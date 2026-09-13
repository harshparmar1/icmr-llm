import os
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models.specialty import Specialty
from backend.app.models.disease import Disease
from backend.app.models.stw_document import STWDocument
from backend.ingestion.models import ExtractedDocument, IngestionResult
from backend.ingestion.pdf_loader import PDFLoader

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Coordinates ICMR STW PDF ingestion, metadata attachment,
    database registration, and serialization into data/processed/.
    """

    def __init__(self, raw_dir: Optional[Path] = None, processed_dir: Optional[Path] = None):
        self.raw_dir = Path(raw_dir or settings.DATA_RAW_DIR)
        self.processed_dir = Path(processed_dir or settings.DATA_PROCESSED_DIR)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.loader = PDFLoader()

    def load_catalog_lookup(self) -> Dict[str, Dict[str, Any]]:
        """
        Builds a lookup table from PDF filename to catalog entry.
        """
        catalog_path = Path(settings.DATA_METADATA_DIR) / "icmr_stw_catalog.json"
        if not catalog_path.exists():
            return {}

        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        lookup = {}
        for entry in catalog:
            url = entry.get("pdf_url", "")
            filename = url.split("/")[-1].split("?")[0]
            lookup[filename] = entry
        return lookup

    def run(self, db: Optional[Session] = None) -> IngestionResult:
        """
        Ingests all PDF files found in data/raw/, records metadata in database,
        and saves extracted JSON to data/processed/.
        """
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True

        catalog_lookup = self.load_catalog_lookup()
        pdf_files = list(self.raw_dir.glob("*.pdf"))
        
        total_docs = len(pdf_files)
        successful = 0
        failed = 0
        total_pages = 0
        extracted_docs: List[ExtractedDocument] = []
        errors: List[Dict[str, str]] = []

        logger.info(f"Found {total_docs} PDF files in {self.raw_dir}")

        for pdf_path in pdf_files:
            try:
                meta = catalog_lookup.get(pdf_path.name, {})
                extracted = self.loader.load_pdf(pdf_path, metadata=meta)

                if extracted.extraction_status == "success" and extracted.total_pages > 0:
                    successful += 1
                    total_pages += extracted.total_pages
                    extracted_docs.append(extracted)

                    # Register in Database
                    self._register_in_db(db, extracted)

                    # Save extracted structured JSON to data/processed/
                    self._save_processed_document(extracted)
                else:
                    failed += 1
                    errors.append({
                        "file": pdf_path.name,
                        "error": extracted.error_message or "Extraction yielded zero pages"
                    })
            except Exception as e:
                failed += 1
                logger.error(f"Failed ingesting {pdf_path.name}: {e}", exc_info=True)
                errors.append({"file": pdf_path.name, "error": str(e)})

        if should_close_db:
            db.close()

        result = IngestionResult(
            total_documents=total_docs,
            successful=successful,
            failed=failed,
            total_pages=total_pages,
            documents=extracted_docs,
            errors=errors
        )

        logger.info(
            f"Ingestion complete: {successful}/{total_docs} successful, "
            f"{total_pages} total pages extracted."
        )
        return result

    def _register_in_db(self, db: Session, doc: ExtractedDocument) -> None:
        """
        Idempotently inserts or updates Specialty, Disease, and STWDocument records.
        """
        specialty_name = doc.specialty or "General Medicine"
        specialty_code = specialty_name.upper().replace(" ", "_")[:30]

        # 1. Specialty
        spec_obj = db.query(Specialty).filter_by(name=specialty_name).first()
        if not spec_obj:
            spec_obj = Specialty(
                code=specialty_code,
                name=specialty_name,
                description=f"Official ICMR STW guidelines for {specialty_name}."
            )
            db.add(spec_obj)
            db.flush()

        # 2. Disease
        disease_name = doc.disease or doc.title or "General Clinical Workflow"
        disease_code = disease_name.upper().replace(" ", "_")[:40]
        
        dis_obj = db.query(Disease).filter_by(code=disease_code).first()
        if not dis_obj:
            dis_obj = Disease(
                specialty_id=spec_obj.id,
                code=disease_code,
                name=disease_name,
                description=f"ICMR Standard Treatment Workflow for {disease_name}."
            )
            db.add(dis_obj)
            db.flush()

        # 3. STWDocument
        title = doc.title
        if not title or title.strip() in ["Standard Treatment Workflow (STW)", "Standard Treatment Workflow"]:
            title = f"ICMR STW: {disease_name}"
        elif not title.startswith("ICMR STW"):
            title = f"ICMR STW: {disease_name}"
            
        stw_obj = db.query(STWDocument).filter_by(file_path=doc.file_path).first()
        if not stw_obj:
            stw_obj = STWDocument(
                specialty_id=spec_obj.id,
                disease_id=dis_obj.id,
                title=title,
                volume="Volume 1",
                official_icmr_url=doc.source_url or "https://www.icmr.gov.in/standard-treatment-workflows-stws",
                file_path=doc.file_path,
                total_pages=doc.total_pages,
                summary=doc.pages[0].text[:400] if doc.pages else None,
                is_active=True
            )
            db.add(stw_obj)
        else:
            stw_obj.total_pages = doc.total_pages
            stw_obj.title = title
            if doc.pages and not stw_obj.summary:
                stw_obj.summary = doc.pages[0].text[:400]

        db.commit()

    def _save_processed_document(self, doc: ExtractedDocument) -> Path:
        """
        Saves extracted document text and per-page data to data/processed/<stem>.json
        """
        stem = Path(doc.file_name).stem
        target = self.processed_dir / f"{stem}_extracted.json"
        payload = {
            "file_name": doc.file_name,
            "title": doc.title,
            "specialty": doc.specialty,
            "disease": doc.disease,
            "source_url": doc.source_url,
            "total_pages": doc.total_pages,
            "extraction_method": doc.extraction_method,
            "pages": [
                {
                    "page_number": p.page_number,
                    "char_count": p.char_count,
                    "is_ocr": p.is_ocr,
                    "text": p.text
                }
                for p in doc.pages
            ]
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return target
