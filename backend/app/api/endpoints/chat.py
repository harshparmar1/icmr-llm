import json
import re
import time
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import sanitize_query_text, mask_sensitive_phi
from backend.app.database.session import get_db
from backend.app.schemas.chat import ChatSymptomRequest, ChatSymptomResponse
from backend.app.schemas.query import EvidenceCitation, SourceReference
from backend.app.schemas.workflow import WorkflowStepBase
from backend.app.rag.retriever import HybridClinicalRetriever
from backend.app.rag.llm import LLMProvider, get_llm_provider
from backend.app.rag.prompts import SYMPTOM_CHATBOT_PROMPT, build_conversational_symptom_prompt
from backend.app.models.specialty import Specialty
from backend.app.models.disease import Disease
from backend.app.models.stw_document import STWDocument
from backend.app.models.query_log import ClinicalQueryLog, QuerySource

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Clinical Chatbot"])

# Cached singletons
_retriever: Optional[HybridClinicalRetriever] = None
_llm_provider: Optional[LLMProvider] = None


def get_chat_retriever() -> HybridClinicalRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridClinicalRetriever()
    return _retriever


def get_chat_llm() -> LLMProvider:
    global _llm_provider
    if _llm_provider is None:
        try:
            _llm_provider = get_llm_provider(settings.LLM_PROVIDER)
        except Exception as e:
            logger.warning(f"Error initializing chat LLM {settings.LLM_PROVIDER}: {e}. Falling back to default.")
            _llm_provider = get_llm_provider("mock")
    return _llm_provider


def _repair_truncated_json(s: str) -> Optional[Dict[str, Any]]:
    s = s.strip()
    if not s.startswith("{"):
        return None
    for suffix in ['"}', '"]}', '"}]}', '"]}}', '"]}}}', '}}', '}']:
        try:
            return json.loads(s + suffix)
        except Exception:
            continue
    return None


def _parse_json_safely(text: str) -> Dict[str, Any]:
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
        pass

    match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    repaired = _repair_truncated_json(cleaned)
    if repaired:
        return repaired

    # Extract reply field via regex if available
    reply_match = re.search(r'"reply"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', cleaned)
    if reply_match:
        reply_val = reply_match.group(1).replace(r'\"', '"').replace(r'\n', '\n')
        return {
            "reply": reply_val,
            "urgency_level": "ROUTINE",
            "condition_matched": "Clinical Guideline",
            "red_flags": [],
            "immediate_actions": [],
            "workflow_steps": [],
            "safety_notice": settings.CLINICAL_SAFETY_DISCLAIMER
        }

    logger.error(f"Failed to parse chat LLM JSON: {cleaned[:120]}...")
    return {
        "reply": cleaned,
        "urgency_level": "ROUTINE",
        "red_flags": [],
        "immediate_actions": [],
        "workflow_steps": [],
        "safety_notice": settings.CLINICAL_SAFETY_DISCLAIMER
    }


def _extract_text(val: Any, default: str = "") -> str:
    """Recursively and intelligently converts dict, list, or primitive into a clean, simple text string."""
    if val is None:
        return default
    if isinstance(val, str):
        cleaned = val.strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            try:
                parsed_json = json.loads(cleaned)
                return _extract_text(parsed_json, default)
            except Exception:
                pass
        return cleaned if cleaned else default
    if isinstance(val, dict):
        # Specific pattern 1: reply with message and explanation
        if "message" in val and "explanation" in val:
            msg = _extract_text(val["message"])
            exp = _extract_text(val["explanation"])
            return f"{msg}\n\n{exp}".strip() if exp else msg
        # Specific pattern 2: action + reason
        if "action" in val and "reason" in val:
            act = _extract_text(val["action"])
            rsn = _extract_text(val["reason"])
            return f"{act} ({rsn})" if rsn else act
        # Specific pattern 3: test / symptom + purpose
        if ("test" in val or "symptom" in val) and "purpose" in val:
            item = _extract_text(val.get("test") or val.get("symptom"))
            purp = _extract_text(val.get("purpose"))
            return f"{item}: {purp}" if purp else item
        # If single key that is a known text container
        if len(val) == 1:
            return _extract_text(next(iter(val.values())), default)
        # General dict: format each key-value clearly
        parts = []
        for k, v in val.items():
            readable_k = k.replace("_", " ").strip().capitalize()
            flat_v = _extract_text(v)
            if flat_v:
                if isinstance(v, (dict, list)):
                    parts.append(f"{readable_k}:\n{flat_v}")
                else:
                    parts.append(f"{readable_k}: {flat_v}")
        return "\n\n".join(parts) if parts else default
    if isinstance(val, (list, tuple)):
        items = [_extract_text(x) for x in val if x]
        if not items:
            return default
        if len(items) > 1:
            return "\n".join(f"• {it.lstrip('•-* ')}" for it in items)
        return items[0]
    return str(val).strip()


def _extract_str_list(val: Any) -> List[str]:
    """Extracts a clean list of strings even if items are dicts or scalar."""
    if not val:
        return []
    if isinstance(val, (list, tuple)):
        items = []
        for x in val:
            if isinstance(x, dict) and "action" in x:
                act = _extract_text(x.get("action"))
                rsn = _extract_text(x.get("reason"))
                text = f"{act} (Note: {rsn})" if rsn else act
            else:
                text = _extract_text(x)
            if text:
                items.append(text)
        return items
    extracted = _extract_text(val)
    return [extracted] if extracted else []


def _detect_conversational_opener(text: str) -> Optional[str]:
    raw = text.strip().lower()
    cleaned = re.sub(r"[^\w\s]", "", raw).strip()
    words = cleaned.split()
    
    # 1. Direct greetings
    greeting_words = {"hi", "hello", "hey", "hiya", "howdy", "hola", "namaste", "greetings"}
    if cleaned in greeting_words or (words and words[0] in greeting_words and len(words) <= 3):
        return (
            "Hello! I am your ICMR Clinical Decision Support and Symptom Triage Assistant. "
            "I can help you understand medical symptoms, disease diagnosis, treatment protocols, "
            "and official ICMR Standard Treatment Workflows.\n\n"
            "How can I assist you with your health or clinical questions today?"
        )

    # 2. Time-of-day greetings
    if any(cleaned == g or cleaned.startswith(g + " ") for g in ["good morning", "good afternoon", "good evening", "good day"]):
        return (
            "Good day! I am your ICMR Clinical Decision Support Assistant. "
            "How can I assist you today with clinical guidance, symptoms, or ICMR Standard Treatment Workflows?"
        )

    # 3. How are you
    if any(p in cleaned for p in ["how are you", "how r u", "how are you doing", "hows it going", "how is it going", "whats up", "what's up"]):
        return (
            "I'm functioning well and ready to assist you! "
            "Feel free to describe any symptoms you are experiencing or ask questions about medical conditions and ICMR clinical guidelines."
        )

    # 4. Identity & capabilities
    if any(p in cleaned for p in ["who are you", "what is your name", "what can you do", "what are you", "tell me about yourself", "how can you help"]):
        return (
            "I am an evidence-grounded Clinical AI Assistant powered by official Indian Council of Medical Research (ICMR) Standard Treatment Workflows.\n\n"
            "Here is how I can help:\n"
            "• **Symptom Triage**: Assess clinical urgency (Routine, Urgent, Emergency)\n"
            "• **Workflow Stages**: Provide official ICMR diagnostic, investigation, and management steps\n"
            "• **Critical Red Flags**: Highlight emergency warning signs requiring immediate hospital care\n"
            "• **Lifestyle & Monitoring**: Evidence-based lifestyle and self-care recommendations\n\n"
            "Please describe any symptoms or ask a medical inquiry to get started!"
        )

    # 5. Gratitude
    if any(cleaned == t or cleaned.startswith(t + " ") for t in ["thank you", "thanks", "thank u", "thx", "thanks a lot", "thank you so much"]):
        return (
            "You are very welcome! Please feel free to ask if you have any further health or clinical questions. Wishing you good health!"
        )

    # 6. Farewell
    if any(cleaned == b or cleaned.startswith(b + " ") for b in ["bye", "goodbye", "see you", "cya", "take care", "good night"]):
        return (
            "Goodbye! Take care, and feel free to return whenever you have health or medical questions."
        )

    return None


NON_MEDICAL_REGEXES = [
    r"\b(python|javascript|typescript|java|c\+\+|c#|golang|rust|php|ruby|swift|html|css|sql|nosql)\b",
    r"\b(write|code|program|script|function|algorithm|class|compiler|regex|git|github|docker|kubernetes)\b",
    r"\b(binary search|quicksort|recursion|linked list|stack|queue|debug|frontend|backend)\b",
    r"\b(cricket|football|soccer|basketball|nba|fifa|ipl|tennis|badminton|olympics|world cup|messi|ronaldo|virat|dhoni|chess)\b",
    r"\b(movie|cinema|actor|actress|hollywood|bollywood|netflix|song|singer|album|lyrics|pop music|hip hop|celebrity)\b",
    r"\b(president|prime minister|parliament|election|vote|political party|politician)\b",
    r"\b(capital of|largest country|continent|mount everest|geography|history of|world war|french revolution)\b",
    r"\b(recipe|how to cook|how to bake|baking|pizza|burger|pasta|biryani|curry recipe|ingredients for)\b",
    r"\b(solve\s+\d+|calculate\s+\d+|derivative of|integral of|speed of light|black hole|solar system|quantum mechanics)\b",
    r"\b(write\s+(a\s+)?(poem|story|essay|song|joke)|tell\s+me\s+(a\s+)?joke)\b"
]

MEDICAL_KEYWORDS = {
    "fever", "cough", "pain", "headache", "chest pain", "back pain", "throat", "vomit",
    "vomiting", "nausea", "diarrhea", "loose motion", "dizziness", "vertigo", "fatigue",
    "tired", "swelling", "edema", "rash", "allergy", "infection", "bleed", "bleeding",
    "breath", "breathing", "dyspnea", "shortness of breath", "palpitation", "seizure",
    "paralysis", "numbness", "tingling", "burn", "burning", "discharge", "wound",
    "ulcer", "cold", "flu", "chills", "sneezing", "congestion", "sinus", "wheezing",
    "heart", "cardio", "kidney", "renal", "lung", "pulmonary", "liver", "hepatic",
    "brain", "neuro", "stomach", "gastric", "abdomen", "bowel", "gut", "eye", "ear",
    "nose", "joint", "muscle", "bone", "spine", "blood", "artery", "vein", "skin",
    "urine", "urinary", "stool", "neck", "pelvis", "pregnancy", "pregnant",
    "hypertension", "blood pressure", "bp", "diabetes", "sugar", "asthma", "copd",
    "rhinosinusitis", "sinusitis", "encephalitis", "meningitis", "stroke", "paralysis",
    "kidney injury", "aki", "ckd", "nephritis", "hyperkalemia", "hypokalemia", "pneumonia",
    "bronchitis", "tuberculosis", "tb", "covid", "dengue", "malaria", "typhoid",
    "jaundice", "hepatitis", "cirrhosis", "cancer", "tumor", "anemia", "thyroid",
    "antenatal", "prenatal", "postnatal", "trimester", "fetal", "fetus",
    "depression", "anxiety", "alcohol", "addiction", "psychiatry", "psychosis",
    "sepsis", "shock", "coma", "syncope", "arrhythmia", "illness", "sick", "disease",
    "medicine", "medication", "drug", "tablet", "pill", "syrup", "injection", "dose",
    "dosage", "antibiotic", "paracetamol", "ibuprofen", "amoxicillin", "treatment",
    "therapy", "cure", "remedy", "diagnosis", "doctor", "physician", "hospital",
    "clinic", "nurse", "icmr", "stw", "guideline", "protocol", "investigation",
    "test", "blood test", "ecg", "xray", "x-ray", "mri", "ct scan", "ultrasound",
    "biopsy", "creatinine", "hemoglobin", "platelet", "vitals", "pulse", "triage",
    "referral", "emergency", "red flag", "symptom", "syndrome", "disorder",
    "patient", "health", "clinical", "hospitalization", "icu", "opd", "dialysis"
}


def _has_medical_intent(text: str) -> bool:
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    words = set(cleaned.split())
    if words.intersection(MEDICAL_KEYWORDS):
        return True
    for kw in MEDICAL_KEYWORDS:
        if " " in kw and kw in cleaned:
            return True
    return False


def _is_strictly_non_medical(text: str) -> bool:
    low = text.lower()
    for pat in NON_MEDICAL_REGEXES:
        if re.search(pat, low):
            return True
    return False


@router.post("/chat", response_model=ChatSymptomResponse, summary="Conversational Symptom Triage & Clinical Workflow")
def conversational_symptom_chat(
    request: ChatSymptomRequest,
    db: Session = Depends(get_db),
    retriever: HybridClinicalRetriever = Depends(get_chat_retriever),
    llm: LLMProvider = Depends(get_chat_llm)
):
    """
    Conversational clinical assistant endpoint:
    1. Responds to casual greetings/intros naturally.
    2. Enforces strict medical-only scope (politely refusing non-medical queries).
    3. Retrieves matching ICMR guidelines from Chroma Cloud.
    4. Synthesizes empathetic conversational guidance, urgency level, red flags,
       and step-by-step ICMR workflow stages.
    5. Audits the query into Supabase PostgreSQL.
    """
    start_time = time.time()

    # 1. Sanitize user input
    clean_message = sanitize_query_text(request.message)
    safe_message = mask_sensitive_phi(clean_message)
    safe_vitals = mask_sensitive_phi(request.patient_vitals) if request.patient_vitals else None

    # Fast-path 1: Conversational greetings, pleasantries, and self-introduction
    greeting_reply = _detect_conversational_opener(safe_message)
    if greeting_reply:
        return ChatSymptomResponse(
            reply=greeting_reply,
            urgency_level="ROUTINE",
            condition_matched="General Inquiry",
            specialty="General Medicine",
            relevant_stw="ICMR Standard Treatment Workflows",
            red_flags=[],
            immediate_actions=[
                "Describe any health symptoms, disease questions, or clinical guidelines to get started."
            ],
            workflow_steps=[],
            evidence=[],
            sources=[],
            safety_notice=settings.CLINICAL_SAFETY_DISCLAIMER
        )

    # Fast-path 2: Out of scope non-medical topics (programming, sports, movies, cooking, etc.)
    if _is_strictly_non_medical(safe_message) and not _has_medical_intent(safe_message):
        return ChatSymptomResponse(
            reply=(
                "I am specialized strictly as an ICMR Clinical and Medical Intelligence Assistant. "
                "I cannot answer questions on non-medical topics (such as programming, sports, "
                "entertainment, politics, history, or general trivia).\n\n"
                "Please feel free to ask questions about health symptoms, medical conditions, "
                "medications, diagnostic investigations, or official ICMR Standard Treatment Workflows!"
            ),
            urgency_level="ROUTINE",
            condition_matched="Out of Scope (Non-Medical)",
            specialty="ICMR Clinical Support",
            relevant_stw="None",
            red_flags=[],
            immediate_actions=[
                "Please enter a medical, clinical, or health-related inquiry."
            ],
            workflow_steps=[],
            evidence=[],
            sources=[],
            safety_notice=settings.CLINICAL_SAFETY_DISCLAIMER
        )

    # 2. Retrieve authoritative ICMR evidence (focused top 3)
    evidence_list = retriever.retrieve(
        query=safe_message,
        top_k=3,
        specialty=request.specialty,
        disease=request.disease
    )
    valid_evidence = [ev for ev in evidence_list if ev.is_above_threshold]

    # If no evidence retrieved: distinguish between non-medical vs medical query
    if not valid_evidence:
        logger.info(f"Low evidence for symptom query '{safe_message[:40]}'")
        if not _has_medical_intent(safe_message):
            # Not medical at all
            return ChatSymptomResponse(
                reply=(
                    "I am specialized strictly as an ICMR Clinical and Medical Intelligence Assistant. "
                    "I do not answer non-medical questions. "
                    "Please ask questions related to health symptoms, medical conditions, or ICMR clinical guidelines."
                ),
                urgency_level="ROUTINE",
                condition_matched="Out of Scope (Non-Medical)",
                specialty="ICMR Clinical Support",
                relevant_stw="None",
                red_flags=[],
                immediate_actions=[
                    "Please ask a medical or health-related question."
                ],
                workflow_steps=[],
                evidence=[],
                sources=[],
                safety_notice=settings.CLINICAL_SAFETY_DISCLAIMER
            )

        # It IS medical, but not in current 9 ICMR STW documents
        return ChatSymptomResponse(
            reply=(
                "I understand your medical inquiry. However, I could not find a direct, "
                "authoritative match within the currently indexed ICMR Standard Treatment Workflows to "
                "provide a specific clinical protocol safely. Please consult a qualified physician or "
                "visit the nearest healthcare facility for a formal clinical evaluation."
            ),
            urgency_level="ROUTINE",
            condition_matched="General Medical Inquiry",
            specialty=request.specialty or "General Medicine",
            relevant_stw="None",
            red_flags=[
                "Difficulty breathing, chest pain, sudden weakness, or loss of consciousness require immediate emergency care."
            ],
            immediate_actions=[
                "Seek an evaluation from a qualified medical doctor.",
                "Keep a log of your symptoms and vitals (temperature, blood pressure, heart rate)."
            ],
            workflow_steps=[],
            evidence=[],
            sources=[],
            safety_notice=settings.CLINICAL_SAFETY_DISCLAIMER
        )

    # 3. Build conversational prompt
    history_dicts = [{"role": m.role, "content": m.content} for m in request.history]
    prompt = build_conversational_symptom_prompt(
        message=safe_message,
        evidence_list=valid_evidence,
        history=history_dicts,
        patient_vitals=safe_vitals
    )

    # 4. Generate response via LLM
    try:
        llm_resp = llm.generate(
            prompt=prompt,
            system_prompt=SYMPTOM_CHATBOT_PROMPT,
            json_mode=True
        )
    except Exception as exc:
        logger.error(f"Chat generation failure: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Clinical chatbot inference failed: {str(exc)}"
        )

    latency_ms = (time.time() - start_time) * 1000
    parsed = _parse_json_safely(llm_resp.content)

    # 5. Extract citations & sources
    citations: List[EvidenceCitation] = [
        EvidenceCitation(**ev.to_citation_dict()) for ev in valid_evidence
    ]

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

    # Workflow steps
    workflow_steps: List[WorkflowStepBase] = []
    raw_steps = parsed.get("workflow_steps", [])
    if isinstance(raw_steps, list):
        for idx, step in enumerate(raw_steps, 1):
            if isinstance(step, dict):
                try:
                    workflow_steps.append(
                        WorkflowStepBase(
                            step_number=int(step.get("step_number") or idx),
                            phase=_extract_text(step.get("phase"), "Management"),
                            title=_extract_text(step.get("title"), "Clinical Action"),
                            description=_extract_text(step.get("description"), ""),
                            page_reference=int(step.get("page_reference") or 1)
                        )
                    )
                except Exception:
                    pass

    # Extract strings safely
    reply_str = _extract_text(
        parsed.get("reply") or parsed.get("message") or parsed.get("guidance"),
        "Clinical guidance derived from official ICMR Standard Treatment Workflows."
    )
    raw_urgency = _extract_text(parsed.get("urgency_level"), "ROUTINE").upper()
    urgency_level = "EMERGENCY" if "EMERG" in raw_urgency else ("URGENT" if "URG" in raw_urgency else "ROUTINE")
    
    immediate_actions = _extract_str_list(parsed.get("immediate_actions", []))
    red_flags = _extract_str_list(parsed.get("red_flags", []))

    primary_disease = _extract_text(parsed.get("condition_matched")) or valid_evidence[0].disease
    primary_specialty = _extract_text(parsed.get("specialty")) or valid_evidence[0].specialty
    primary_stw = _extract_text(parsed.get("relevant_stw")) or valid_evidence[0].stw_title

    # 6. Audit to Supabase PostgreSQL
    try:
        spec_row = db.query(Specialty).filter(Specialty.name.ilike(f"%{primary_specialty}%")).first()
        dis_row = db.query(Disease).filter(Disease.name.ilike(f"%{primary_disease}%")).first()
        doc_row = db.query(STWDocument).filter(STWDocument.title.ilike(f"%{primary_stw}%")).first()

        log_entry = ClinicalQueryLog(
            query_text=f"[CHATBOT] {safe_message}",
            specialty_id=spec_row.id if spec_row else None,
            disease_id=dis_row.id if dis_row else None,
            retrieved_stw_id=doc_row.id if doc_row else None,
            response_summary=reply_str[:1000],
            llm_provider=settings.LLM_PROVIDER,
            latency_ms=round(latency_ms, 2),
            is_grounded=bool(valid_evidence)
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)

        for ev in valid_evidence:
            qs = QuerySource(
                query_log_id=log_entry.id,
                stw_document_id=doc_row.id if doc_row else 1,
                chunk_id=ev.chunk_id,
                page_number=ev.page_number,
                section=ev.section_title or primary_specialty,
                similarity_score=ev.relevance_score,
                excerpt=ev.content[:500]
            )
            db.add(qs)
        db.commit()
    except Exception as db_err:
        logger.warning(f"Error logging chat to Supabase: {db_err}")
        db.rollback()

    return ChatSymptomResponse(
        reply=reply_str,
        urgency_level=urgency_level,
        condition_matched=primary_disease,
        specialty=primary_specialty,
        relevant_stw=primary_stw,
        red_flags=red_flags,
        immediate_actions=immediate_actions,
        workflow_steps=workflow_steps,
        evidence=citations,
        sources=sources,
        safety_notice=settings.CLINICAL_SAFETY_DISCLAIMER
    )
