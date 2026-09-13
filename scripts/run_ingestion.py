import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.database.session import init_db, SessionLocal
from backend.ingestion.downloader import ICMRDownloader
from backend.ingestion.pipeline import IngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ingestion_runner")


def main():
    parser = argparse.ArgumentParser(description="ICMR STW PDF Ingestion CLI")
    parser.add_argument("--download-core", action="store_true", help="Download core representative official ICMR STWs")
    parser.add_argument("--limit", type=int, default=8, help="Number of documents to download for core dataset")
    args = parser.parse_args()

    # Ensure DB tables exist
    init_db()

    if args.download_core:
        logger.info(f"Downloading up to {args.limit} official ICMR STW PDFs from verified portal...")
        downloader = ICMRDownloader()
        downloader.download_core_dataset(max_documents=args.limit)

    logger.info("Executing ICMR PDF Ingestion Pipeline...")
    pipeline = IngestionPipeline()
    db = SessionLocal()
    try:
        result = pipeline.run(db=db)
        print("\n====================================================")
        print("ICMR INGESTION PIPELINE EXECUTION SUMMARY")
        print("====================================================")
        print(f"Total PDFs Scanned:      {result.total_documents}")
        print(f"Successfully Extracted:  {result.successful}")
        print(f"Failed:                  {result.failed}")
        print(f"Total Pages Extracted:   {result.total_pages}")
        if result.errors:
            print("\nErrors Encountered:")
            for err in result.errors:
                print(f" - {err['file']}: {err['error']}")
        print("====================================================\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
