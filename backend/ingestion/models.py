from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class RawDocumentPage:
    page_number: int  # 1-indexed
    text: str
    char_count: int
    tables: List[List[List[str]]] = field(default_factory=list)
    is_ocr: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDocument:
    file_path: str
    file_name: str
    total_pages: int
    pages: List[RawDocumentPage]
    title: Optional[str] = None
    specialty: Optional[str] = None
    disease: Optional[str] = None
    source_url: Optional[str] = None
    extraction_method: str = "pymupdf"
    extraction_status: str = "success"
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(f"--- Page {p.page_number} ---\n{p.text}" for p in self.pages)


@dataclass
class IngestionResult:
    total_documents: int
    successful: int
    failed: int
    total_pages: int
    documents: List[ExtractedDocument] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ClinicalSection:
    title: str
    section_type: str  # OVERVIEW, ASSESSMENT, INVESTIGATION, MANAGEMENT, RED_FLAGS, REFERRAL, FOLLOW_UP, GENERAL
    content: str
    page_number: int
    char_count: int = 0


@dataclass
class ClinicalChunk:
    chunk_id: str
    file_name: str
    stw_title: str
    specialty: str
    disease: str
    volume: Optional[str]
    page_number: int
    section_title: str
    section_type: str
    content: str
    context_header: str
    full_chunk_text: str
    source_url: Optional[str]
    chunk_index: int
    char_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

