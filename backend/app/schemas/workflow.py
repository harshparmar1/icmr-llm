from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class WorkflowStepBase(BaseModel):
    step_number: int
    phase: str  # Initial Assessment, Investigation, Diagnosis / Classification, Management, Follow-up, Referral
    title: str
    description: str
    mandatory_actions: Optional[str] = None
    contraindications: Optional[str] = None
    red_flags: Optional[str] = None
    page_reference: int
    icmr_section: Optional[str] = None


class WorkflowStepCreate(WorkflowStepBase):
    stw_document_id: int
    disease_id: int


class WorkflowStepOut(WorkflowStepBase):
    id: int
    stw_document_id: int
    disease_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowGraphOut(BaseModel):
    disease_id: int
    disease_name: str
    specialty_name: str
    stw_title: str
    stw_id: int
    steps: List[WorkflowStepOut]
