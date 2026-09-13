from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class RetrievedEvidence:
    """
    Standardized evidence unit returned by the hybrid retrieval engine.
    Enforces strict citation traceability to official ICMR STW documents.
    """
    chunk_id: str
    stw_title: str
    specialty: str
    disease: str
    page_number: int
    section_title: str
    section_type: str
    content: str
    context_header: str
    relevance_score: float
    dense_score: float = 0.0
    bm25_score: float = 0.0
    is_above_threshold: bool = True
    volume: Optional[str] = "Volume 1"
    source_url: Optional[str] = "https://www.icmr.gov.in/standard-treatment-workflows-stws"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_citation_dict(self) -> Dict[str, Any]:
        """Converts to API EvidenceCitation format."""
        return {
            "chunk_id": self.chunk_id,
            "stw_title": self.stw_title,
            "specialty": self.specialty,
            "disease": self.disease,
            "volume": self.volume,
            "page": self.page_number,
            "section": f"{self.section_title} ({self.section_type})",
            "source_url": self.source_url,
            "similarity_score": round(self.relevance_score, 4),
            "retrieved_evidence": self.content
        }
