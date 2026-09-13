from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DiseaseBase(BaseModel):
    specialty_id: int
    code: str
    name: str
    icd10_code: Optional[str] = None
    description: Optional[str] = None


class DiseaseCreate(DiseaseBase):
    pass


class DiseaseOut(DiseaseBase):
    id: int
    created_at: datetime
    specialty_name: Optional[str] = None
    stw_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)
