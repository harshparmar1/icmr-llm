import json
import time
import re
from typing import Optional, Dict, Any

from backend.app.rag.llm.base import LLMProvider, LLMResponse
from backend.app.core.config import settings


class MockLLMProvider(LLMProvider):
    """
    Offline deterministic clinical LLM adapter.
    Constructs faithful, grounded JSON responses directly from provided ICMR evidence,
    or generates safe refusal when evidence is absent.
    """

    def __init__(self, model_name: str = "mock-clinical-engine"):
        self._model = model_name

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = True,
        temperature: float = 0.1,
        max_tokens: int = 1500
    ) -> LLMResponse:
        start_time = time.time()

        # Check if prompt contains explicit insufficient evidence marker
        if "INSUFFICIENT_EVIDENCE" in prompt or "NO_RELEVANT_EVIDENCE" in prompt:
            payload = {
                "summary": "Insufficient ICMR evidence was retrieved to answer this safely.",
                "workflow_steps": [],
                "limitations": [
                    "No authoritative ICMR Standard Treatment Workflow matching this specific inquiry was retrieved."
                ],
                "safety_notice": settings.CLINICAL_SAFETY_DISCLAIMER
            }
            latency = (time.time() - start_time) * 1000
            return LLMResponse(
                content=json.dumps(payload, indent=2),
                model=self.model_name,
                provider=self.provider_name,
                latency_ms=round(latency, 2)
            )

        # Parse query from prompt
        query_match = re.search(r"CLINICAL QUERY:\s*(.+?)(?:\n|$)", prompt, re.IGNORECASE)
        query_text = query_match.group(1).strip() if query_match else "Clinical Query"

        # Parse specialty, disease, and document from evidence headers
        specialty_match = re.search(r"Specialty:\s*([^\|\n]+)", prompt)
        specialty_name = specialty_match.group(1).strip() if specialty_match else None

        disease_match = re.search(r"Disease:\s*([^\|\n]+)", prompt)
        disease_name = disease_match.group(1).strip() if disease_match else None

        doc_match = re.search(r"Document:\s*([^\n]+)", prompt)
        doc_name = doc_match.group(1).strip() if doc_match else None

        # Fallback to bracketed headers if not found
        if not disease_name or not specialty_name:
            stw_match = re.search(r"\[ICMR STW:\s*([^\|\]]+)(?:\|\s*(?:Specialty:\s*)?([^\|\]]+))?", prompt)
            if stw_match:
                disease_name = disease_name or stw_match.group(1).strip()
                if stw_match.group(2):
                    specialty_name = specialty_name or stw_match.group(2).strip()

        disease_name = disease_name or "Clinical Condition"
        specialty_name = specialty_name or "General Medicine"
        stw_title = doc_name or f"ICMR STW: {disease_name}"

        # Extract page number if available
        page_match = re.search(r"Page:\s*(\d+)", prompt)
        page_ref = int(page_match.group(1)) if page_match else 1

        # Extract evidence lines from prompt (both bullets and ICMR Text content)
        evidence_lines = []
        in_icmr_text = False
        for line in prompt.split("\n"):
            line_str = line.strip()
            if line_str.startswith("ICMR Text:"):
                in_icmr_text = True
                continue
            elif line_str.startswith("---") or line_str.startswith("INSTRUCTIONS:"):
                in_icmr_text = False

            if in_icmr_text and line_str and not line_str.startswith("---"):
                evidence_lines.append(line_str)
            elif (line_str.startswith("•") or line_str.startswith("-")) and not line_str.startswith("---"):
                evidence_lines.append(line_str.lstrip("•- "))

        # Synthesize workflow steps from evidence lines
        workflow_steps = []
        for idx, item in enumerate(evidence_lines[:5], 1):
            phase = "Management"
            if any(w in item.lower() for w in ["screen", "history", "assessment", "exam"]):
                phase = "Initial Assessment"
            elif any(w in item.lower() for w in ["investigat", "test", "cbc", "usg", "ct", "ecg", "creatinine"]):
                phase = "Investigation"
            elif any(w in item.lower() for w in ["refer", "urgent", "dialysis", "emergency"]):
                phase = "Referral"
            elif any(w in item.lower() for w in ["follow", "monitor"]):
                phase = "Follow-up"

            workflow_steps.append({
                "step_number": idx,
                "phase": phase,
                "title": item[:60] + ("..." if len(item) > 60 else ""),
                "description": item,
                "page_reference": page_ref
            })

        summary = (
            f"Based on the official ICMR Standard Treatment Workflow for {disease_name}, "
            f"standard clinical management emphasizes evidence-grounded assessment and stepwise interventions."
        )
        if evidence_lines:
            summary += f" Key recommendations include: {'; '.join(evidence_lines[:3])}."

        payload = {
            "query": query_text,
            "specialty": specialty_name,
            "disease": disease_name,
            "relevant_stw": stw_title,
            "summary": summary,
            "workflow_steps": workflow_steps,
            "limitations": [
                "Guideline is advisory and feasibility considerations depend on the healthcare tier (Primary/Secondary/Tertiary).",
                "Clinical discretion must be exercised for individualized patient presentation."
            ],
            "safety_notice": settings.CLINICAL_SAFETY_DISCLAIMER
        }

        latency = (time.time() - start_time) * 1000

        return LLMResponse(
            content=json.dumps(payload, indent=2),
            model=self.model_name,
            provider=self.provider_name,
            latency_ms=round(latency, 2)
        )
