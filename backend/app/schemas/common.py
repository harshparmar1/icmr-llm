from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthCheck(BaseModel):
    status: str = "healthy"
    app_name: str
    version: str
    environment: str
    database_connected: bool
    chromadb_ready: bool
    llm_provider: str


class StandardResponse(BaseModel, Generic[T]):
    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    details: Optional[Any] = None


class PaginationParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
