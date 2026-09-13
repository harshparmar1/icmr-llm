import json
import re
import logging
from typing import Optional, List, Dict, Any

from backend.app.core.config import settings
from backend.app.schemas.query import ClinicalQueryResponse, EvidenceCitation, SourceReference
from backend.app.schemas.workflow import WorkflowStepBase
from backend.app.rag.retriever import HybridClinicalRetriever
from backend.app.rag.llm import LLMProvider, get_llm_provider
from backend.app.rag.prompts import SYSTEM_CLINICAL_PROMPT, build_clinical_rag_prompt

logger = logging.getLogger(__name__)


class RAGGenerator:
    """
    Orchestrates end-to-end RAG clinical generation:
    1. Retrieval via HybridClinicalRetriever
    2. Threshold safety validation
    3. Prompt construction with strict grounding instructions
    4. Multi-provider LLM/SLM invocation
    5. Structured JSON validation and citation binding
    """

    def __init__(
        self,
        retriever: Optional[HybridClinicalRetriever] = None,
        llm_provider: Optional[LLMProvider] = None
    ):
        self.retriever = retriever or HybridClinicalRetriever()
        self.llm = llm_provider or get_llm_provider()

    def generate_response(
        self,
        query: str,
        specialty: Optional[str] = None,
        disease: Optional[str] = None,
        patient_context: Optional[str] = None,
        top_k: int = 5,
        min_relevance: Optional[float] = None
    ) -> ClinicalQueryResponse:
        """
        Executes grounded clinical decision support for user query.
        """
        # 1. Retrieve hybrid evidence
        evidence_list = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            specialty=specialty,
            disease=disease,
            min_relevance=min_relevance
        )

        # 2. Check evidence sufficiency
        valid_evidence = [ev for ev in evidence_list if ev.is_above_threshold]

        if not valid_evidence:
            logger.info(f"Refusing query '{query[:40]}' due to insufficient evidence.")
            return ClinicalQueryResponse(
                query=query,
                specialty=specialty,
                disease=disease,
                relevant_stw="None",
                summary="Insufficient ICMR evidence was retrieved to answer this safely.",
                workflow_steps=[],
                evidence=[],
                sources=[],
                limitations=[
                    "No authoritative ICMR Standard Treatment Workflow matching this specific inquiry was retrieved."
                ],
                safety_notice=settings.CLINICAL_SAFETY_DISCLAIMER
            )

        # 3. Construct prompt
        prompt = build_clinical_rag_prompt(
            query=query,
            evidence_list=valid_evidence,
            patient_context=patient_context
        )

        # 4. Generate response from LLM / SLM
        llm_resp = self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_CLINICAL_PROMPT,
            json_mode=True
        )

        # 5. Parse and validate structured output
        parsed_json = self._parse_json_safely(llm_resp.content)

        # 6. Assemble citations and source references
        citations: List[EvidenceCitation] = [
            EvidenceCitation(**ev.to_citation_dict()) for ev in valid_evidence
        ]

        # Group sources by STW title
        source_map: Dict[str, Dict[str, Any]] = {}
        for ev in valid_evidence:
            if ev.stw_title not in source_map:
                source_map[ev.stw_title] = {
                    "stw_title": ev.stw_title,
                    "specialty": ev.specialty,
                    "disease": ev.disease,
                    "volume": ev.volume,
                    "pages": set(),
                    "official_url": ev.source_url
                }
            source_map[ev.stw_title]["pages"].add(ev.page_number)

        sources: List[SourceReference] = [
            SourceReference(
                stw_title=s["stw_title"],
                specialty=s["specialty"],
                disease=s["disease"],
                volume=s["volume"],
                pages=sorted(list(s["pages"])),
                official_url=s["official_url"]
            )
            for s in source_map.values()
        ]

        workflow_steps: List[WorkflowStepBase] = []
        raw_steps = parsed_json.get("workflow_steps", [])
        for step in raw_steps:
            try:
                workflow_steps.append(
                    WorkflowStepBase(
                        step_number=step.get("step_number", 1),
                        phase=step.get("phase", "Management"),
                        title=step.get("title", "Clinical Action"),
                        description=step.get("description", ""),
                        page_reference=step.get("page_reference", 1)
                    )
                )
            except Exception as step_err:
                logger.debug(f"Skipping malformed step: {step_err}")

        # Primary disease / specialty attribution
        primary_disease = parsed_json.get("disease") or valid_evidence[0].disease
        primary_specialty = parsed_json.get("specialty") or valid_evidence[0].specialty
        primary_stw = parsed_json.get("relevant_stw") or valid_evidence[0].stw_title

        return ClinicalQueryResponse(
            query=query,
            specialty=primary_specialty,
            disease=primary_disease,
            relevant_stw=primary_stw,
            summary=parsed_json.get("summary", "Guideline summary unavailable."),
            workflow_steps=workflow_steps,
            evidence=citations,
            sources=sources,
            limitations=parsed_json.get("limitations", [
                "Feasibility depends on the healthcare tier (Primary/Secondary/Tertiary).",
                "Follow clinical judgement alongside ICMR guidelines."
            ]),
            safety_notice=parsed_json.get("safety_notice", settings.CLINICAL_SAFETY_DISCLAIMER)
        )

    def _parse_json_safely(self, text: str) -> Dict[str, Any]:
        """Safely parses JSON even if enclosed in markdown code fences."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except Exception:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            logger.error(f"Failed to parse LLM JSON output: {cleaned[:100]}...")
            return {
                "summary": cleaned,
                "workflow_steps": [],
                "limitations": [],
                "safety_notice": settings.CLINICAL_SAFETY_DISCLAIMER
            }
