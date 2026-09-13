import time
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import sanitize_query_text, mask_sensitive_phi
from backend.app.database.session import get_db
from backend.app.schemas.query import ClinicalQueryRequest, ClinicalQueryResponse
from backend.app.rag.generation import RAGGenerator
from backend.app.rag.llm.factory import get_llm_provider
from backend.app.models.specialty import Specialty
from backend.app.models.disease import Disease
from backend.app.models.stw_document import STWDocument
from backend.app.models.query_log import ClinicalQueryLog, QuerySource

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Clinical Query"])

# Cache or instantiate generator
_generator: Optional[RAGGenerator] = None


def get_rag_generator() -> RAGGenerator:
    global _generator
    if _generator is None:
        try:
            llm = get_llm_provider(settings.LLM_PROVIDER)
            _generator = RAGGenerator(llm_provider=llm)
        except Exception as e:
            logger.warning(f"Failed to initialize default provider {settings.LLM_PROVIDER}: {e}. Falling back to default.")
            _generator = RAGGenerator()
    return _generator


@router.post("/query", response_model=ClinicalQueryResponse, summary="Execute Grounded ICMR Clinical Query")
def execute_clinical_query(
    request: ClinicalQueryRequest,
    db: Session = Depends(get_db),
    generator: RAGGenerator = Depends(get_rag_generator)
):
    """
    Executes an evidence-grounded clinical decision support query against official ICMR STWs.
    
    1. Sanitizes query and redacts any patient identifiers (PHI).
    2. Resolves specialty and disease filters from database IDs or names.
    3. Retrieves grounded chunks from Chroma Cloud vector store.
    4. Generates structured clinical workflow stages using Mistral AI.
    5. Audits the query and retrieved citations in Supabase PostgreSQL.
    """
    start_time = time.time()

    # 1. Sanitize input
    cleaned_query = sanitize_query_text(request.query)
    safe_query = mask_sensitive_phi(cleaned_query)
    safe_context = mask_sensitive_phi(request.patient_context) if request.patient_context else None

    # 2. Resolve specialty and disease names
    specialty_name = request.specialty
    disease_name = request.disease
    matched_spec = None
    matched_disease = None

    if request.specialty_id:
        matched_spec = db.query(Specialty).filter(Specialty.id == request.specialty_id).first()
        if matched_spec:
            specialty_name = matched_spec.name

    if request.disease_id:
        matched_disease = db.query(Disease).filter(Disease.id == request.disease_id).first()
        if matched_disease:
            disease_name = matched_disease.name

    # 3. Generate clinical workflow via RAG
    try:
        response = generator.generate_response(
            query=safe_query,
            specialty=specialty_name,
            disease=disease_name,
            patient_context=safe_context
        )
    except Exception as exc:
        logger.error(f"RAG Generation error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Clinical workflow generation failed: {str(exc)}"
        )

    latency_ms = (time.time() - start_time) * 1000

    # 4. Audit query log and sources in Supabase PostgreSQL
    try:
        # Match disease & STW if not resolved
        if not matched_spec and response.specialty:
            matched_spec = db.query(Specialty).filter(Specialty.name.ilike(f"%{response.specialty}%")).first()
        if not matched_disease and response.disease:
            matched_disease = db.query(Disease).filter(Disease.name.ilike(f"%{response.disease}%")).first()
        
        matched_doc = None
        if response.relevant_stw and response.relevant_stw != "None":
            matched_doc = db.query(STWDocument).filter(STWDocument.title.ilike(f"%{response.relevant_stw}%")).first()

        log_entry = ClinicalQueryLog(
            query_text=safe_query,
            specialty_id=matched_spec.id if matched_spec else (request.specialty_id or None),
            disease_id=matched_disease.id if matched_disease else (request.disease_id or None),
            retrieved_stw_id=matched_doc.id if matched_doc else None,
            response_summary=(response.summary[:1000] if response.summary else ""),
            llm_provider=settings.LLM_PROVIDER,
            latency_ms=round(latency_ms, 2),
            is_grounded=bool(response.evidence)
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)

        # Audit citation sources
        for ev in response.evidence:
            doc_id = matched_doc.id if matched_doc else 1
            qs = QuerySource(
                query_log_id=log_entry.id,
                stw_document_id=doc_id,
                chunk_id=ev.chunk_id,
                page_number=ev.page,
                section=ev.section or response.specialty or "General",
                similarity_score=ev.similarity_score,
                excerpt=ev.retrieved_evidence[:500]
            )
            db.add(qs)
        db.commit()
    except Exception as db_err:
        logger.warning(f"Failed to audit query log to Supabase: {db_err}")
        db.rollback()

    return response


@router.get("/recent", summary="Retrieve Recent Clinical Queries")
def get_recent_queries(limit: int = 10, db: Session = Depends(get_db)):
    """Returns recent clinical queries from Supabase audit logs."""
    try:
        logs = db.query(ClinicalQueryLog).order_by(ClinicalQueryLog.created_at.desc()).limit(limit).all()
        return [
            {
                "id": log.id,
                "query": log.query_text,
                "summary": log.response_summary,
                "llm_provider": log.llm_provider,
                "latency_ms": log.latency_ms,
                "is_grounded": log.is_grounded,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]
    except Exception as e:
        logger.warning(f"Error fetching recent query logs: {e}")
        return []
