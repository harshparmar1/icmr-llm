import json
import logging
from pathlib import Path
import sys

# Ensure root directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.core.config import settings
from backend.ingestion.models import ClinicalChunk
from backend.app.rag.vector_store import ChromaVectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("indexing_runner")


def main():
    chunks_path = settings.DATA_PROCESSED_DIR / "icmr_clinical_chunks.json"
    if not chunks_path.exists():
        logger.error(f"Chunks file not found at {chunks_path}. Run scripts/run_chunking.py first.")
        return

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)

    logger.info(f"Loaded {len(chunks_data)} clinical chunks from {chunks_path}")

    # Reconstruct ClinicalChunk objects
    chunks = [
        ClinicalChunk(
            chunk_id=c["chunk_id"],
            file_name=c["file_name"],
            stw_title=c["stw_title"],
            specialty=c["specialty"],
            disease=c["disease"],
            volume=c.get("volume", "Volume 1"),
            page_number=c["page_number"],
            section_title=c["section_title"],
            section_type=c["section_type"],
            content=c["content"],
            context_header=c["context_header"],
            full_chunk_text=c["full_chunk_text"],
            source_url=c.get("source_url"),
            chunk_index=c["chunk_index"],
            char_count=c["char_count"],
            metadata=c.get("metadata", {})
        )
        for c in chunks_data
    ]

    logger.info("Initializing ChromaDB Vector Store...")
    vector_store = ChromaVectorStore()
    
    # Reset collection for clean index
    vector_store.reset_collection()

    # Index chunks
    added_count = vector_store.add_chunks(chunks, batch_size=32)

    print("\n====================================================")
    print("ICMR CHROMADB VECTOR INDEXING SUMMARY")
    print("====================================================")
    print(f"Target Backend:          {'Chroma Cloud' if vector_store.use_cloud and settings.CHROMA_API_KEY else 'Local PersistentClient'}")
    print(f"Collection Name:         {vector_store.collection_name}")
    print(f"Total Chunks Indexed:    {added_count}")
    print(f"Total Vectors in Store:  {vector_store.count()}")
    print("====================================================\n")

    # Run quick clinical verification query
    print("Running Verification Semantic Queries:")
    test_queries = [
        "What is the management of hyperkalemia in acute kidney injury?",
        "First-line drug therapy for hypertension in adults",
        "Indications for urgent referral or dialysis in kidney disease"
    ]

    for q in test_queries:
        print(f"\n[Query]: '{q}'")
        results = vector_store.similarity_search(q, top_k=2)
        for rank, r in enumerate(results, 1):
            meta = r["metadata"]
            print(f"  #{rank} Score: {r['similarity_score']:.4f} | STW: {meta.get('disease')} | Section: {meta.get('section_title')} (Page {meta.get('page_number')})")
            print(f"     Excerpt: {r['document'][:140]}...\n")


if __name__ == "__main__":
    main()
