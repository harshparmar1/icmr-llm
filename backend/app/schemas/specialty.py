from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class SpecialtyBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class SpecialtyCreate(SpecialtyBase):
    pass


class SpecialtyOut(SpecialtyBase):
    id: int
    created_at: datetime
    disease_count: Optional[int] = 0
    stw_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)
