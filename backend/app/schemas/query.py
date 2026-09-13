from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from backend.app.schemas.workflow import WorkflowStepBase


class EvidenceCitation(BaseModel):
    chunk_id: Optional[str] = None
    stw_title: str
    specialty: str
    disease: str
    volume: Optional[str] = None
    page: int
    section: Optional[str] = None
    source_url: Optional[str] = None
    similarity_score: float
    retrieved_evidence: str


class SourceReference(BaseModel):
    stw_id: Optional[int] = None
    stw_title: str
    specialty: str
    disease: str
    volume: Optional[str] = None
    pages: List[int]
    official_url: Optional[str] = None


class ClinicalQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Clinical inquiry or workflow question")
    specialty_id: Optional[int] = Field(None, description="Optional specialty filter")
    disease_id: Optional[int] = Field(None, description="Optional disease filter")
    specialty: Optional[str] = Field(None, description="Optional specialty name filter")
    disease: Optional[str] = Field(None, description="Optional disease name filter")
    patient_context: Optional[str] = Field(None, max_length=1000, description="Optional clinical/patient context")


class ClinicalQueryResponse(BaseModel):
    query: str
    specialty: Optional[str] = None
    disease: Optional[str] = None
    relevant_stw: Optional[str] = None
    summary: str
    workflow_steps: List[WorkflowStepBase] = []
    evidence: List[EvidenceCitation] = []
    sources: List[SourceReference] = []
    limitations: List[str] = []
    safety_notice: str


class SearchRequest(BaseModel):
    keyword: str = Field(..., min_length=2, max_length=200)
    specialty_id: Optional[int] = None
    disease_id: Optional[int] = None
    top_k: int = 10


class SearchResultItem(BaseModel):
    stw_id: int
    title: str
    specialty: str
    disease: str
    volume: Optional[str] = None
    snippet: str
    score: float


class SearchResponse(BaseModel):
    total: int
    results: List[SearchResultItem]


# STW Compliance Checker Schemas
class RecordedWorkflowStep(BaseModel):
    step_number: Optional[int] = None
    action_taken: str
    performed_at_stage: Optional[str] = None  # e.g., "Assessment", "Investigation", "Management"
    notes: Optional[str] = None


class ComplianceCheckRequest(BaseModel):
    disease_id: int
    recorded_steps: List[RecordedWorkflowStep]
    clinical_notes: Optional[str] = None


class ComplianceStepEvaluation(BaseModel):
    step_number: int
    expected_step_title: str
    phase: str
    status: str  # "COMPLETED", "POTENTIAL_DEVIATION", "NOT_DOCUMENTED"
    rationale: str
    icmr_page: int
    icmr_guideline: str


class ComplianceCheckResponse(BaseModel):
    disease_name: str
    specialty_name: str
    stw_title: str
    total_expected_steps: int
    completed_steps_count: int
    potential_deviations_count: int
    not_documented_count: int
    evaluations: List[ComplianceStepEvaluation]
    summary_advisory: str
    safety_disclaimer: str
