import json
import logging
from pathlib import Path
import sys

# Ensure root directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.core.config import settings
from backend.ingestion.models import ExtractedDocument, RawDocumentPage
from backend.ingestion.chunker import ClinicalChunker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("chunking_runner")


def main():
    processed_dir = settings.DATA_PROCESSED_DIR
    extracted_files = list(processed_dir.glob("*_extracted.json"))
    
    if not extracted_files:
        logger.warning(f"No extracted JSON files found in {processed_dir}. Run scripts/run_ingestion.py first.")
        return

    logger.info(f"Processing {len(extracted_files)} extracted documents for clinical chunking...")
    chunker = ClinicalChunker()
    total_chunks = []

    for fpath in extracted_files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        pages = [
            RawDocumentPage(
                page_number=p["page_number"],
                text=p["text"],
                char_count=p["char_count"],
                is_ocr=p.get("is_ocr", False)
            )
            for p in data.get("pages", [])
        ]

        doc = ExtractedDocument(
            file_path=str(settings.DATA_RAW_DIR / data["file_name"]),
            file_name=data["file_name"],
            total_pages=data["total_pages"],
            pages=pages,
            title=data.get("title"),
            specialty=data.get("specialty"),
            disease=data.get("disease"),
            source_url=data.get("source_url"),
            extraction_method=data.get("extraction_method", "pymupdf"),
            metadata=data
        )

        doc_chunks = chunker.chunk_document(doc)
        total_chunks.extend(doc_chunks)

    # Convert chunks to JSON-serializable dictionaries
    output_path = processed_dir / "icmr_clinical_chunks.json"
    serializable_chunks = [
        {
            "chunk_id": c.chunk_id,
            "file_name": c.file_name,
            "stw_title": c.stw_title,
            "specialty": c.specialty,
            "disease": c.disease,
            "volume": c.volume,
            "page_number": c.page_number,
            "section_title": c.section_title,
            "section_type": c.section_type,
            "content": c.content,
            "context_header": c.context_header,
            "full_chunk_text": c.full_chunk_text,
            "source_url": c.source_url,
            "chunk_index": c.chunk_index,
            "char_count": c.char_count,
            "metadata": c.metadata
        }
        for c in total_chunks
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable_chunks, f, indent=2, ensure_ascii=False)

    print("\n====================================================")
    print("ICMR CLINICAL CHUNKING EXECUTION SUMMARY")
    print("====================================================")
    print(f"Documents Chunked:       {len(extracted_files)}")
    print(f"Total Chunks Generated:  {len(total_chunks)}")
    print(f"Output File:             {output_path}")

    # Display section type distribution
    sec_counts = {}
    for c in total_chunks:
        sec_counts[c.section_type] = sec_counts.get(c.section_type, 0) + 1

    print("\nSection Type Distribution:")
    for stype, count in sorted(sec_counts.items(), key=lambda x: -x[1]):
        print(f" - {stype:<15}: {count} chunks")
    print("====================================================\n")


if __name__ == "__main__":
    main()
