from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database.base import Base


class Disease(Base):
    __tablename__ = "diseases"

    id = Column(Integer, primary_key=True, index=True)
    specialty_id = Column(Integer, ForeignKey("specialties.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), index=True, nullable=False)
    icd10_code = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    specialty = relationship("Specialty", back_populates="diseases")
    stw_documents = relationship("STWDocument", back_populates="disease", cascade="all, delete-orphan")
    workflow_steps = relationship("WorkflowStep", back_populates="disease", cascade="all, delete-orphan")
