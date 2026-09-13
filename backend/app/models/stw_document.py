from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.app.database.base import Base


class STWDocument(Base):
    __tablename__ = "stw_documents"

    id = Column(Integer, primary_key=True, index=True)
    specialty_id = Column(Integer, ForeignKey("specialties.id", ondelete="RESTRICT"), nullable=False, index=True)
    disease_id = Column(Integer, ForeignKey("diseases.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    title = Column(String(300), index=True, nullable=False)
    volume = Column(String(50), nullable=True)  # e.g., "Volume 1", "Volume 2"
    edition = Column(String(50), nullable=True)  # e.g., "2019", "2022"
    official_icmr_url = Column(String(500), nullable=True)
    file_path = Column(String(500), nullable=False)
    total_pages = Column(Integer, default=1)
    publication_year = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    specialty = relationship("Specialty", back_populates="stw_documents")
    disease = relationship("Disease", back_populates="stw_documents")
    workflow_steps = relationship("WorkflowStep", back_populates="stw_document", cascade="all, delete-orphan")
    query_sources = relationship("QuerySource", back_populates="stw_document")
