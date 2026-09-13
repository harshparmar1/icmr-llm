import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.api.models.Collection import Collection

from backend.app.core.config import settings
from backend.app.rag.embeddings import get_embedding_service, EmbeddingService
from backend.ingestion.models import ClinicalChunk

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """
    Manages the ChromaDB vector collection for ICMR STW clinical chunks.
    Supports both Chroma Cloud (remote managed cluster) and local PersistentClient fallback.
    """

    def __init__(
        self,
        collection_name: Optional[str] = None,
        use_cloud: Optional[bool] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.use_cloud = use_cloud if use_cloud is not None else settings.CHROMA_USE_CLOUD
        self.embedding_service = embedding_service or get_embedding_service()
        self.client = self._init_client()
        self.collection = self._get_or_create_collection()

    def _init_client(self) -> chromadb.ClientAPI:
        """
        Initializes Chroma client: prefers Chroma Cloud when configured,
        with automatic fallback to local disk persistence if offline or unconfigured.
        """
        if self.use_cloud and settings.CHROMA_API_KEY:
            try:
                logger.info(
                    f"Connecting to Chroma Cloud (Tenant: {settings.CHROMA_TENANT}, "
                    f"Database: {settings.CHROMA_DATABASE})..."
                )
                client = chromadb.CloudClient(
                    api_key=settings.CHROMA_API_KEY,
                    tenant=settings.CHROMA_TENANT,
                    database=settings.CHROMA_DATABASE
                )
                # Verify heartbeat
                client.heartbeat()
                logger.info("Connected to Chroma Cloud successfully.")
                return client
            except Exception as e:
                logger.warning(
                    f"Could not connect to Chroma Cloud ({e}). Falling back to local PersistentClient."
                )

        # Local filesystem fallback
        persist_dir = Path(settings.CHROMA_PERSIST_DIRECTORY)
        persist_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using local Chroma PersistentClient at {persist_dir}")
        return chromadb.PersistentClient(path=str(persist_dir))

    def _get_or_create_collection(self) -> Collection:
        """
        Retrieves or initializes the clinical chunks collection with cosine similarity.
        """
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine", "description": "ICMR Standard Treatment Workflow Clinical Chunks"}
        )

    def add_chunks(self, chunks: List[ClinicalChunk], batch_size: int = 50) -> int:
        """
        Generates dense vector embeddings and upserts clinical chunks into ChromaDB.
        """
        if not chunks:
            return 0

        total_added = 0
        logger.info(f"Upserting {len(chunks)} clinical chunks into collection '{self.collection_name}'...")

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            ids = [c.chunk_id for c in batch]
            documents = [c.full_chunk_text for c in batch]
            
            # Generate embeddings
            embeddings = self.embedding_service.embed_batch(documents)

            # Sanitize metadata (Chroma requires primitive types: str, int, float, bool)
            metadatas = []
            for c in batch:
                meta = {
                    "chunk_id": str(c.chunk_id),
                    "stw_title": str(c.stw_title),
                    "specialty": str(c.specialty),
                    "disease": str(c.disease),
                    "volume": str(c.volume or "Volume 1"),
                    "page_number": int(c.page_number),
                    "section_title": str(c.section_title),
                    "section_type": str(c.section_type),
                    "source_url": str(c.source_url or ""),
                    "file_name": str(c.file_name),
                    "char_count": int(c.char_count)
                }
                metadatas.append(meta)

            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            total_added += len(batch)

        logger.info(f"Successfully upserted {total_added} chunks. Collection total: {self.count()}")
        return total_added

    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic similarity search against the ICMR STW vector collection.
        Returns matched documents with metadata and cosine similarity scores.
        """
        query_vec = self.embedding_service.embed_text(query)

        query_params = {
            "query_embeddings": [query_vec],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"]
        }
        if where:
            query_params["where"] = where

        results = self.collection.query(**query_params)

        matched_items = []
        if results and results["ids"] and len(results["ids"][0]) > 0:
            for idx in range(len(results["ids"][0])):
                chunk_id = results["ids"][0][idx]
                doc_text = results["documents"][0][idx]
                meta = results["metadatas"][0][idx] if results.get("metadatas") else {}
                distance = results["distances"][0][idx] if results.get("distances") else 0.0
                
                # Cosine distance to similarity: similarity = 1 - distance
                similarity_score = max(0.0, min(1.0, 1.0 - float(distance)))

                matched_items.append({
                    "chunk_id": chunk_id,
                    "document": doc_text,
                    "metadata": meta,
                    "similarity_score": round(similarity_score, 4),
                    "distance": round(float(distance), 4)
                })

        return matched_items

    def count(self) -> int:
        """Returns total vector count in the collection."""
        return self.collection.count()

    def reset_collection(self) -> None:
        """Clears the collection to allow fresh indexing."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection()
            logger.info(f"Collection '{self.collection_name}' has been reset.")
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
