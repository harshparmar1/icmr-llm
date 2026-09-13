from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from backend.app.schemas.workflow import WorkflowStepBase
from backend.app.schemas.query import EvidenceCitation, SourceReference


import json


def _coerce_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        cleaned = v.strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            try:
                parsed_json = json.loads(cleaned)
                return _coerce_str(parsed_json)
            except Exception:
                pass
        return cleaned
    if isinstance(v, dict):
        if "message" in v and "explanation" in v:
            msg = _coerce_str(v["message"])
            exp = _coerce_str(v["explanation"])
            return f"{msg}\n\n{exp}".strip() if exp else msg
        if "action" in v and "reason" in v:
            act = _coerce_str(v["action"])
            rsn = _coerce_str(v["reason"])
            return f"{act} ({rsn})" if rsn else act
        if ("test" in v or "symptom" in v) and "purpose" in v:
            item = _coerce_str(v.get("test") or v.get("symptom"))
            purp = _coerce_str(v.get("purpose"))
            return f"{item}: {purp}" if purp else item
        if len(v) == 1:
            return _coerce_str(next(iter(v.values())))
        parts = []
        for k, val in v.items():
            readable_k = k.replace("_", " ").strip().capitalize()
            flat_val = _coerce_str(val)
            if flat_val:
                if isinstance(val, (dict, list)):
                    parts.append(f"{readable_k}:\n{flat_val}")
                else:
                    parts.append(f"{readable_k}: {flat_val}")
        return "\n\n".join(parts)
    if isinstance(v, (list, tuple)):
        items = [_coerce_str(item) for item in v if item]
        if not items:
            return ""
        if len(items) > 1:
            return "\n".join(f"• {it.lstrip('•-* ')}" for it in items)
        return items[0]
    return str(v).strip()


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Text content of the message")


class ChatSymptomRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=1000, description="Patient symptoms or clinical question")
    history: List[ChatMessage] = Field(default=[], description="Previous conversation turns")
    specialty: Optional[str] = Field(None, description="Optional specialty filter")
    disease: Optional[str] = Field(None, description="Optional disease filter")
    patient_vitals: Optional[str] = Field(None, max_length=500, description="Optional vitals or lab parameters")


class ChatSymptomResponse(BaseModel):
    reply: str = Field(..., description="Conversational clinical guidance and explanation")
    urgency_level: str = Field(default="ROUTINE", description="'EMERGENCY', 'URGENT', or 'ROUTINE'")
    condition_matched: Optional[str] = None
    specialty: Optional[str] = None
    relevant_stw: Optional[str] = None
    red_flags: List[str] = []
    workflow_steps: List[WorkflowStepBase] = []
    evidence: List[EvidenceCitation] = []
    sources: List[SourceReference] = []
    immediate_actions: List[str] = []
    safety_notice: str

    @field_validator("reply", mode="before")
    @classmethod
    def validate_reply(cls, v: Any) -> str:
        res = _coerce_str(v)
        return res if res else "Clinical guidance derived from official ICMR recommendations."

    @field_validator("urgency_level", mode="before")
    @classmethod
    def validate_urgency(cls, v: Any) -> str:
        s = _coerce_str(v).upper()
        if "EMERG" in s:
            return "EMERGENCY"
        if "URG" in s:
            return "URGENT"
        return "ROUTINE"

    @field_validator("immediate_actions", "red_flags", mode="before")
    @classmethod
    def validate_str_list(cls, v: Any) -> List[str]:
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            items = []
            for item in v:
                text = _coerce_str(item)
                if text:
                    items.append(text)
            return items
        text = _coerce_str(v)
        return [text] if text else []
