from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from backend.app.schemas.workflow import WorkflowStepOut


class STWDocumentBase(BaseModel):
    specialty_id: int
    disease_id: int
    title: str
    volume: Optional[str] = None
    edition: Optional[str] = None
    official_icmr_url: Optional[str] = None
    file_path: str
    total_pages: int = 1
    publication_year: Optional[int] = None
    summary: Optional[str] = None
    is_active: bool = True


class STWDocumentCreate(STWDocumentBase):
    pass


class STWDocumentOut(STWDocumentBase):
    id: int
    created_at: datetime
    specialty_name: Optional[str] = None
    disease_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class STWDocumentDetail(STWDocumentOut):
    workflow_steps: List[WorkflowStepOut] = []

    model_config = ConfigDict(from_attributes=True)
