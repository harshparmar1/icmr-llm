from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database.base import Base


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id = Column(Integer, primary_key=True, index=True)
    stw_document_id = Column(Integer, ForeignKey("stw_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    disease_id = Column(Integer, ForeignKey("diseases.id", ondelete="CASCADE"), nullable=False, index=True)
    
    step_number = Column(Integer, nullable=False)
    phase = Column(String(100), nullable=False)  # Initial Assessment, Investigation, Diagnosis, Management, Follow-up, Referral
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    mandatory_actions = Column(Text, nullable=True)  # JSON or newline-separated criteria
    contraindications = Column(Text, nullable=True)
    red_flags = Column(Text, nullable=True)
    page_reference = Column(Integer, nullable=False, default=1)
    icmr_section = Column(String(150), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    stw_document = relationship("STWDocument", back_populates="workflow_steps")
    disease = relationship("Disease", back_populates="workflow_steps")
