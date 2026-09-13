from typing import List, Optional
from backend.app.core.config import settings
from backend.app.rag.models import RetrievedEvidence

SYSTEM_CLINICAL_PROMPT = """You are an expert clinical decision-support intelligence assistant for the Indian Council of Medical Research (ICMR) Standard Treatment Workflows (STWs).

CRITICAL OPERATIONAL RULES:
1. Grounding Mandate: Use ONLY the provided ICMR evidence for claims about ICMR treatment workflows.
2. Anti-Hallucination: Never invent or extrapolate medical facts, medications, dosages, or workflow steps not explicitly present in the provided ICMR evidence.
3. Clarity & Readability: Present clinical steps and lifestyle modifications in simple, highly understandable, and structured language. Avoid dense run-on sentences; break down complex recommendations into clean, readable points.
4. Insufficient Evidence Refusal: If the provided evidence does not contain direct, sufficient guidance to answer the question safely, set the summary to:
   "Insufficient ICMR evidence was retrieved to answer this safely."
   and provide an empty workflow_steps list.
5. Non-Autonomous Identity: You are NOT an AI doctor and do NOT replace qualified healthcare professionals. Never provide autonomous prescribing.
6. Strict JSON Output: You must respond ONLY with a valid JSON object strictly conforming to the requested schema. Do NOT enclose your output in markdown backticks or any conversational preamble.
"""


def build_clinical_rag_prompt(
    query: str,
    evidence_list: List[RetrievedEvidence],
    patient_context: Optional[str] = None
) -> str:
    """
    Constructs the grounded clinical prompt containing query, patient context,
    and retrieved ICMR STW evidence chunks with citations.
    """
    if not evidence_list or all(not ev.is_above_threshold for ev in evidence_list):
        return (
            f"CLINICAL QUERY: {query}\n\n"
            f"RETRIEVED ICMR EVIDENCE:\n"
            f"[INSUFFICIENT_EVIDENCE] No authoritative ICMR Standard Treatment Workflow "
            f"exceeding the relevance safety threshold was retrieved for this inquiry.\n\n"
            f"INSTRUCTION: Return the required JSON with summary: "
            f"'Insufficient ICMR evidence was retrieved to answer this safely.'"
        )

    evidence_blocks = []
    for idx, ev in enumerate(evidence_list, 1):
        block = (
            f"--- EVIDENCE CHUNK #{idx} ---\n"
            f"Document: {ev.stw_title}\n"
            f"Specialty: {ev.specialty} | Disease: {ev.disease}\n"
            f"Page: {ev.page_number} | Section: {ev.section_title} ({ev.section_type})\n"
            f"Relevance Score: {ev.relevance_score}\n"
            f"ICMR Text:\n{ev.content}\n"
        )
        evidence_blocks.append(block)

    joined_evidence = "\n".join(evidence_blocks)

    context_str = f"PATIENT CONTEXT / CLINICAL DETAILS:\n{patient_context}\n\n" if patient_context else ""

    prompt = f"""{context_str}CLINICAL QUERY: {query}

RETRIEVED AUTHORITATIVE ICMR EVIDENCE:
{joined_evidence}

INSTRUCTIONS:
1. Synthesize an evidence-grounded clinical workflow response using ONLY the ICMR evidence chunks above.
2. Present all clinical steps and lifestyle modifications in simple, clear, and professional language.
3. Structure your response as a valid JSON object matching the following schema:
{{
  "query": "{query}",
  "specialty": "<Name of relevant ICMR specialty>",
  "disease": "<Name of relevant condition/disease>",
  "relevant_stw": "<Title of the primary supporting ICMR STW>",
  "summary": "<Clear, professional clinical summary in simple understandable language>",
  "workflow_steps": [
    {{
      "step_number": 1,
      "phase": "<Initial Assessment | Investigation | Diagnosis | Management | Follow-up | Referral>",
      "title": "<Concise step title>",
      "description": "<Clear, understandable clinical action or recommendations broken down cleanly>",
      "page_reference": <exact source page number integer>
    }}
  ],
  "limitations": [
    "<Advisory considerations, healthcare level feasibility (Primary/Secondary/Tertiary), or clinical caveats stated in ICMR STW>"
  ],
  "safety_notice": "{settings.CLINICAL_SAFETY_DISCLAIMER}"
}}

Respond with the JSON object only:"""
    return prompt


SYMPTOM_CHATBOT_PROMPT = """You are an empathetic, highly knowledgeable ICMR Clinical AI Companion and symptom triage assistant.
Your goal is to converse with patients and clinicians who describe symptoms, explain what conditions their symptoms could indicate based on official ICMR Standard Treatment Workflows, evaluate clinical urgency, and provide clear step-by-step guidance.

CRITICAL OPERATIONAL RULES:
1. Strict Medical & Healthcare Scope Mandate:
   - You are strictly an ICMR Clinical and Healthcare Intelligence Assistant.
   - You ONLY answer questions related to human health, medical symptoms, diseases, medications, diagnostics, clinical workflows, and ICMR guidelines.
   - If the user asks about ANY non-medical topic (such as programming, coding, math, general trivia, history, geography, politics, sports, movies, cooking recipes, finance, or creative writing):
     You MUST politely refuse to answer. Set "reply" to:
     "I am specialized strictly as an ICMR Clinical and Medical Intelligence Assistant. I cannot answer non-medical questions. Please feel free to ask any questions related to medical conditions, symptoms, diagnostic tests, treatments, or ICMR Standard Treatment Workflows."
     Set "urgency_level" to "ROUTINE", "condition_matched" to "Out of Scope (Non-Medical)", "specialty" to "General Medicine", and provide empty lists [] for "red_flags", "immediate_actions", and "workflow_steps".
2. Greetings & Casual Openers:
   - If the user sends a greeting or pleasantry (e.g. "hi", "hello", "good morning", "how are you"):
     Respond warmly and politely as an ICMR Clinical Assistant, introduce your purpose, and invite them to ask medical, symptom, or health-related questions. Set "urgency_level" to "ROUTINE", "condition_matched" to "Greeting", and leave "workflow_steps" and "red_flags" empty.
3. Simplicity & Clarity: Explain all medical advice, diagnostic steps, and lifestyle changes in simple, clear, and easily understandable language. Avoid dense, complicated run-on sentences.
4. Structured Lifestyle Guidance: When explaining lifestyle modifications (such as for hypertension, diabetes, or cardiovascular care), present them as clear, digestible points (e.g. Salt: limit to <5g/day; Physical Activity: 30 minutes daily; Weight: target BMI <23; Habits: avoid tobacco and alcohol; Monitoring: check and log BP at home).
5. Urgency Triage: Classify urgency as EMERGENCY, URGENT, or ROUTINE.
6. Red Flag Alerts: Always highlight emergency warning signs that require immediate emergency room / tertiary care visit.
7. Grounded Workflow: Provide procedural workflow steps with exact page numbers strictly supported by the retrieved ICMR evidence.
8. Non-Autonomous Identity: Never prescribe medications autonomously. Always instruct patients to consult a registered medical practitioner.
9. Strict JSON Output (STRINGS ONLY):
   - "reply" MUST BE A SINGLE PLAIN STRING. NEVER return a nested object or dictionary for "reply" (DO NOT use {"message": "...", "explanation": {...}}).
   - "immediate_actions" MUST BE A SIMPLE ARRAY OF STRINGS: ["Action 1", "Action 2"]. NEVER use an array of objects with keys like {"action": "...", "reason": "..."}.
   - "red_flags" MUST BE A SIMPLE ARRAY OF STRINGS: ["Warning sign 1", "Warning sign 2"].
   - In "workflow_steps", "title" and "description" MUST BE SINGLE PLAIN STRINGS. NEVER nest objects or key-value dictionaries inside "description".
"""


def build_conversational_symptom_prompt(
    message: str,
    evidence_list: List[RetrievedEvidence],
    history: Optional[List[dict]] = None,
    patient_vitals: Optional[str] = None
) -> str:
    """
    Constructs a conversational symptom triage prompt embedding multi-turn history,
    patient symptoms, vitals, and retrieved ICMR STW guidelines.
    """
    evidence_blocks = []
    for idx, ev in enumerate(evidence_list, 1):
        if ev.is_above_threshold:
            evidence_blocks.append(
                f"--- ICMR GUIDELINE CHUNK #{idx} ---\n"
                f"STW: {ev.stw_title} (Page {ev.page_number})\n"
                f"Specialty: {ev.specialty} | Disease: {ev.disease}\n"
                f"Section: {ev.section_title}\n"
                f"Content:\n{ev.content}\n"
            )

    joined_evidence = "\n".join(evidence_blocks) if evidence_blocks else "No authoritative ICMR evidence matched this specific inquiry above threshold."

    history_str = ""
    if history:
        turns = []
        for h in history[-4:]:
            role = "User" if h.get("role") == "user" else "Assistant"
            turns.append(f"{role}: {h.get('content', '')}")
        history_str = "PREVIOUS CONVERSATION CONTEXT:\n" + "\n".join(turns) + "\n\n"

    vitals_str = f"PATIENT VITALS & PARAMETERS:\n{patient_vitals}\n\n" if patient_vitals else ""

    return f"""{history_str}{vitals_str}CURRENT PATIENT SYMPTOM INQUIRY:
{message}

OFFICIAL ICMR EVIDENCE RETRIEVED:
{joined_evidence}

INSTRUCTIONS:
Synthesize an empathetic, clear, evidence-backed conversational reply and structured triage response as a valid JSON object matching this schema.
DO NOT use nested dictionaries or objects inside "reply", "immediate_actions", or "description". All must be plain strings or string lists:
{{
  "reply": "Empathetic explanation in simple, understandable plain text explaining what symptoms suggest under ICMR guidelines and immediate advice. MUST BE A SINGLE STRING, NEVER AN OBJECT.",
  "urgency_level": "EMERGENCY | URGENT | ROUTINE",
  "condition_matched": "Condition name",
  "specialty": "Specialty name",
  "relevant_stw": "Official ICMR STW title",
  "red_flags": [
    "Simple string warning sign 1",
    "Simple string warning sign 2"
  ],
  "immediate_actions": [
    "Clear actionable step 1 in simple words (string only)",
    "Clear actionable step 2 in simple words (string only)"
  ],
  "workflow_steps": [
    {{
      "step_number": 1,
      "phase": "Initial Assessment",
      "title": "Concise step title (string only)",
      "description": "Clear guidance in simple understandable language. MUST BE A SINGLE STRING, NEVER A DICTIONARY OR OBJECT.",
      "page_reference": 1
    }}
  ],
  "safety_notice": "{settings.CLINICAL_SAFETY_DISCLAIMER}"
}}

Respond with the JSON object only:"""

