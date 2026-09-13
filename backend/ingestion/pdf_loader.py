import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import unicodedata
import pymupdf as fitz

from backend.ingestion.models import RawDocumentPage, ExtractedDocument

logger = logging.getLogger(__name__)

# Minimum characters expected on a standard text-based PDF page
MIN_TEXT_CHARS_THRESHOLD = 50


class PDFLoader:
    """
    Robust clinical PDF extraction engine using PyMuPDF (fitz)
    with optional table extraction and OCR fallback for scanned pages.
    """

    def __init__(self, enable_ocr_fallback: bool = True, ocr_threshold: int = MIN_TEXT_CHARS_THRESHOLD):
        self.enable_ocr_fallback = enable_ocr_fallback
        self.ocr_threshold = ocr_threshold

    def load_pdf(self, file_path: str | Path, metadata: Optional[Dict[str, Any]] = None) -> ExtractedDocument:
        """
        Extracts all pages, text, and structure from an ICMR STW PDF file.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        meta = metadata or {}
        extracted_pages: List[RawDocumentPage] = []
        extraction_method = "pymupdf"

        try:
            doc = fitz.open(str(path))
            total_pages = len(doc)
            
            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_number = page_idx + 1  # 1-indexed
                
                # 1. Native PyMuPDF text extraction
                text = page.get_text("text") or ""
                # Normalize unicode ligatures (e.g. \ufb02 'fl', \ufb01 'fi') to standard ascii/utf-8 characters
                text = unicodedata.normalize("NFKD", text).strip()
                is_ocr = False

                # 2. Scanned page detection & OCR fallback
                if len(text) < self.ocr_threshold and self.enable_ocr_fallback:
                    ocr_text = self._attempt_ocr(page)
                    if ocr_text and len(ocr_text) > len(text):
                        text = ocr_text.strip()
                        is_ocr = True
                        extraction_method = "pymupdf+ocr"

                extracted_pages.append(
                    RawDocumentPage(
                        page_number=page_number,
                        text=text,
                        char_count=len(text),
                        is_ocr=is_ocr,
                        metadata={"page_dimensions": [page.rect.width, page.rect.height]}
                    )
                )

            doc.close()

            return ExtractedDocument(
                file_path=str(path.resolve()),
                file_name=path.name,
                total_pages=total_pages,
                pages=extracted_pages,
                title=meta.get("title") or self._infer_title(extracted_pages, path.name),
                specialty=meta.get("specialty"),
                disease=meta.get("disease"),
                source_url=meta.get("source_url"),
                extraction_method=extraction_method,
                extraction_status="success",
                metadata=meta
            )

        except Exception as e:
            logger.error(f"Error extracting PDF {path.name}: {str(e)}", exc_info=True)
            return ExtractedDocument(
                file_path=str(path.resolve()),
                file_name=path.name,
                total_pages=0,
                pages=[],
                extraction_method=extraction_method,
                extraction_status="failed",
                error_message=str(e),
                metadata=meta
            )

    def _attempt_ocr(self, page: fitz.Page) -> Optional[str]:
        """
        Renders a PDF page to an image and runs Tesseract OCR if available.
        """
        try:
            import pytesseract
            from PIL import Image
            import io

            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes))
            
            ocr_text = pytesseract.image_to_string(image)
            return ocr_text
        except Exception as ocr_err:
            logger.debug(f"OCR fallback unavailable or failed: {ocr_err}")
            return None

    def _infer_title(self, pages: List[RawDocumentPage], fallback_name: str) -> str:
        """
        Infers document title from the first page text header, filtering out
        common boilerplate lines (e.g., ICMR headers, disclaimers).
        """
        boilerplate_keywords = [
            "standard treatment workflow",
            "this stw has been prepared",
            "indian council of medical research",
            "ministry of health",
            "government of india",
            "national health authority",
            "department of health",
            "page ",
            "icd-11",
            "icd-10"
        ]

        if pages and pages[0].text:
            lines = [l.strip() for l in pages[0].text.split("\n") if l.strip()]
            for line in lines[:10]:
                lower_line = line.lower()
                if any(bp in lower_line for bp in boilerplate_keywords):
                    continue
                # Accept clinical disease titles
                if 3 < len(line) < 80:
                    return line.title()

        # Fallback to cleaned filename
        clean_name = re.sub(r"^\d+_", "", fallback_name)
        clean_name = clean_name.replace(".pdf", "").replace("_final", "").replace("_", " ").strip()
        return clean_name.title()
