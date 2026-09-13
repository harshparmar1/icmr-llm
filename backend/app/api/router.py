import os
import time
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.schemas.common import HealthCheck, StandardResponse
from backend.app.api.endpoints.query import router as query_router
from backend.app.api.endpoints.stws import router as stws_router
from backend.app.api.endpoints.chat import router as chat_router

api_router = APIRouter(prefix="/api")
api_router.include_router(query_router)
api_router.include_router(stws_router)
api_router.include_router(chat_router)


@api_router.get("/health", response_model=HealthCheck, tags=["System Health"])
def health_check(db: Session = Depends(get_db)):
    """
    Evaluates system operational status, database connectivity, and configured AI provider.
    """
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    chroma_ready = os.path.exists(settings.CHROMA_PERSIST_DIRECTORY)

    return HealthCheck(
        status="healthy" if db_connected else "degraded",
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database_connected=db_connected,
        chromadb_ready=chroma_ready,
        llm_provider=settings.LLM_PROVIDER
    )


@api_router.get("/health/db", tags=["System Health"])
def db_health_check(db: Session = Depends(get_db)):
    """
    Dedicated database ping test returning dialect and connectivity status.
    """
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "dialect": db.bind.dialect.name if db.bind else "unknown",
            "url_type": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )
