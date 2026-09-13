from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from backend.app.database.base import Base


class ClinicalQueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    specialty_id = Column(Integer, ForeignKey("specialties.id", ondelete="SET NULL"), nullable=True)
    disease_id = Column(Integer, ForeignKey("diseases.id", ondelete="SET NULL"), nullable=True)
    retrieved_stw_id = Column(Integer, ForeignKey("stw_documents.id", ondelete="SET NULL"), nullable=True)
    response_summary = Column(Text, nullable=True)
    llm_provider = Column(String(50), default="mock")
    latency_ms = Column(Float, default=0.0)
    is_grounded = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sources = relationship("QuerySource", back_populates="query_log", cascade="all, delete-orphan")


class QuerySource(Base):
    __tablename__ = "query_sources"

    id = Column(Integer, primary_key=True, index=True)
    query_log_id = Column(Integer, ForeignKey("query_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    stw_document_id = Column(Integer, ForeignKey("stw_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(100), nullable=True)
    page_number = Column(Integer, nullable=False, default=1)
    section = Column(String(150), nullable=True)
    similarity_score = Column(Float, default=0.0)
    excerpt = Column(Text, nullable=False)

    # Relationships
    query_log = relationship("ClinicalQueryLog", back_populates="sources")
    stw_document = relationship("STWDocument", back_populates="query_sources")
