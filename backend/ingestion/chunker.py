import re
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from backend.ingestion.models import ExtractedDocument, ClinicalSection, ClinicalChunk
from backend.ingestion.text_cleaner import ClinicalTextCleaner
from backend.ingestion.section_detector import ClinicalSectionDetector

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHUNK_CHARS = 750
DEFAULT_CHUNK_OVERLAP = 120


class ClinicalChunker:
    """
    Transforms extracted ICMR STW documents into structured,
    evidence-grounded clinical chunks with full metadata and section awareness.
    """

    def __init__(
        self,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    ):
        self.max_chunk_chars = max_chunk_chars
        self.chunk_overlap = chunk_overlap
        self.cleaner = ClinicalTextCleaner()
        self.section_detector = ClinicalSectionDetector()

    def chunk_document(self, doc: ExtractedDocument) -> List[ClinicalChunk]:
        """
        Processes an ExtractedDocument:
        1. Cleans each page's text.
        2. Detects clinical sections.
        3. Generates bounded chunks retaining clinical coherence.
        4. Injects contextual breadcrumbs and metadata.
        """
        all_chunks: List[ClinicalChunk] = []
        global_chunk_idx = 1

        disease_name = doc.disease or doc.title or "Clinical Guideline"
        specialty_name = doc.specialty or "General Medicine"
        
        spec_slug = re.sub(r"[^A-Z0-9]", "", specialty_name.upper())[:6] or "GEN"
        dis_slug = re.sub(r"[^A-Z0-9]", "", disease_name.upper())[:8] or "MED"

        for page in doc.pages:
            # 1. Clean page text
            cleaned_text = self.cleaner.clean_page_text(page.text)
            if not cleaned_text or len(cleaned_text) < 20:
                continue

            # 2. Segment into clinical sections
            sections = self.section_detector.detect_sections(cleaned_text, page.page_number)

            for sec in sections:
                # 3. Chunk the section
                sec_text = sec.content
                if not sec_text:
                    continue

                if len(sec_text) <= self.max_chunk_chars:
                    # Single coherent section chunk
                    chunk_obj = self._create_chunk(
                        doc=doc,
                        page_number=page.page_number,
                        section=sec,
                        content=sec_text,
                        chunk_index=global_chunk_idx,
                        spec_slug=spec_slug,
                        dis_slug=dis_slug
                    )
                    all_chunks.append(chunk_obj)
                    global_chunk_idx += 1
                else:
                    # Multi-chunk segmented with overlap
                    sub_chunks = self._split_text_with_overlap(sec_text)
                    for sub_text in sub_chunks:
                        chunk_obj = self._create_chunk(
                            doc=doc,
                            page_number=page.page_number,
                            section=sec,
                            content=sub_text,
                            chunk_index=global_chunk_idx,
                            spec_slug=spec_slug,
                            dis_slug=dis_slug
                        )
                        all_chunks.append(chunk_obj)
                        global_chunk_idx += 1

        logger.info(
            f"Generated {len(all_chunks)} clinical chunks for {doc.file_name} "
            f"({doc.total_pages} pages, {len(all_chunks)} chunks)"
        )
        return all_chunks

    def _split_text_with_overlap(self, text: str) -> List[str]:
        """
        Splits text by paragraphs/lines while respecting max_chunk_chars and overlap.
        """
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        chunks = []
        current_lines = []
        current_len = 0

        for line in paragraphs:
            line_len = len(line)
            if current_len + line_len > self.max_chunk_chars and current_lines:
                chunk_str = "\n".join(current_lines).strip()
                chunks.append(chunk_str)

                # Keep overlap lines
                overlap_lines = []
                overlap_len = 0
                for rev_line in reversed(current_lines):
                    if overlap_len + len(rev_line) <= self.chunk_overlap:
                        overlap_lines.insert(0, rev_line)
                        overlap_len += len(rev_line)
                    else:
                        break
                current_lines = overlap_lines + [line]
                current_len = sum(len(l) for l in current_lines) + len(current_lines)
            else:
                current_lines.append(line)
                current_len += line_len + 1

        if current_lines:
            final_str = "\n".join(current_lines).strip()
            if not chunks or final_str != chunks[-1]:
                chunks.append(final_str)

        return chunks

    def _create_chunk(
        self,
        doc: ExtractedDocument,
        page_number: int,
        section: ClinicalSection,
        content: str,
        chunk_index: int,
        spec_slug: str,
        dis_slug: str
    ) -> ClinicalChunk:
        """
        Assembles a ClinicalChunk object with deterministic ID and contextual header.
        """
        chunk_id = f"ICMR-{spec_slug}-{dis_slug}-P{page_number:02d}-C{chunk_index:03d}"
        disease_name = doc.disease or doc.title or "Clinical Guideline"
        specialty_name = doc.specialty or "General Medicine"

        context_header = (
            f"[ICMR STW: {disease_name} | Specialty: {specialty_name} | "
            f"Section: {section.title} ({section.section_type}) | Page: {page_number}]"
        )
        full_text = f"{context_header}\n{content}"

        return ClinicalChunk(
            chunk_id=chunk_id,
            file_name=doc.file_name,
            stw_title=doc.title or f"ICMR STW: {disease_name}",
            specialty=specialty_name,
            disease=disease_name,
            volume=doc.metadata.get("volume", "Volume 1"),
            page_number=page_number,
            section_title=section.title,
            section_type=section.section_type,
            content=content,
            context_header=context_header,
            full_chunk_text=full_text,
            source_url=doc.source_url or "https://www.icmr.gov.in/standard-treatment-workflows-stws",
            chunk_index=chunk_index,
            char_count=len(content),
            metadata={
                "specialty": specialty_name,
                "disease": disease_name,
                "section_type": section.section_type,
                "section_title": section.title,
                "page_number": page_number,
                "file_name": doc.file_name,
                "char_count": len(content),
                "source_url": doc.source_url or "https://www.icmr.gov.in/standard-treatment-workflows-stws"
            }
        )
