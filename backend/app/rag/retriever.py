import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from backend.app.core.config import settings
from backend.app.rag.models import RetrievedEvidence
from backend.app.rag.vector_store import ChromaVectorStore
from backend.app.rag.bm25_retriever import BM25ClinicalRetriever

logger = logging.getLogger(__name__)


class HybridClinicalRetriever:
    """
    Hybrid Clinical Retrieval Engine combining:
    - Dense Semantic Search via ChromaDB
    - Lexical Keyword Search via BM25
    - Clinical Metadata Filtering (specialty, disease, section_type)
    - Relevance Scoring & Clinical Threshold Validation
    """

    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        bm25_retriever: Optional[BM25ClinicalRetriever] = None,
        dense_weight: float = None,
        bm25_weight: float = None,
        enable_hybrid: bool = None,
        relevance_threshold: float = None
    ):
        self.vector_store = vector_store or ChromaVectorStore()
        self.bm25 = bm25_retriever or BM25ClinicalRetriever()
        self.dense_weight = dense_weight if dense_weight is not None else settings.DENSE_WEIGHT
        self.bm25_weight = bm25_weight if bm25_weight is not None else settings.BM25_WEIGHT
        self.enable_hybrid = enable_hybrid if enable_hybrid is not None else settings.ENABLE_HYBRID_RETRIEVAL
        self.relevance_threshold = relevance_threshold if relevance_threshold is not None else settings.RETRIEVAL_RELEVANCE_THRESHOLD

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        specialty: Optional[str] = None,
        disease: Optional[str] = None,
        section_type: Optional[str] = None,
        min_relevance: Optional[float] = None
    ) -> List[RetrievedEvidence]:
        """
        Executes hybrid retrieval for a clinical query with optional metadata filters.
        Returns evidence chunks ranked by fused relevance score.
        """
        k = top_k or settings.RETRIEVAL_TOP_K
        threshold = min_relevance if min_relevance is not None else self.relevance_threshold

        # Construct metadata filter
        where_filter: Dict[str, Any] = {}
        if specialty:
            where_filter["specialty"] = specialty
        if disease:
            where_filter["disease"] = disease
        if section_type:
            where_filter["section_type"] = section_type

        # ChromaDB requires '$and' for multiple filter conditions
        if len(where_filter) > 1:
            where_clause = {"$and": [{k: v} for k, v in where_filter.items()]}
        elif len(where_filter) == 1:
            where_clause = where_filter
        else:
            where_clause = None

        # 1. Dense Semantic Retrieval
        dense_results: List[Dict[str, Any]] = []
        try:
            dense_results = self.vector_store.similarity_search(
                query=query,
                top_k=k * 2 if self.enable_hybrid else k,
                where=where_clause
            )
        except Exception as e:
            logger.error(f"Dense vector retrieval failed: {e}")

        # 2. BM25 Lexical Keyword Retrieval
        bm25_results: List[Dict[str, Any]] = []
        if self.enable_hybrid:
            try:
                bm25_results = self.bm25.search(
                    query=query,
                    top_k=k * 2,
                    where=where_clause
                )
            except Exception as e:
                logger.error(f"BM25 retrieval failed: {e}")

        # 3. Score Fusion (Weighted Linear Combination)
        fused_candidates: Dict[str, Dict[str, Any]] = {}

        # Ingest dense matches
        for item in dense_results:
            cid = item["chunk_id"]
            fused_candidates[cid] = {
                "chunk_id": cid,
                "document": item["document"],
                "metadata": item["metadata"],
                "dense_score": item["similarity_score"],
                "bm25_score": 0.0
            }

        # Ingest BM25 matches
        for item in bm25_results:
            cid = item["chunk_id"]
            if cid in fused_candidates:
                fused_candidates[cid]["bm25_score"] = item["bm25_score"]
            else:
                fused_candidates[cid] = {
                    "chunk_id": cid,
                    "document": item["document"],
                    "metadata": item["metadata"],
                    "dense_score": 0.0,
                    "bm25_score": item["bm25_score"]
                }

        # Compute fused relevance score
        ranked_evidence: List[RetrievedEvidence] = []
        for cid, candidate in fused_candidates.items():
            d_score = candidate["dense_score"]
            b_score = candidate["bm25_score"]

            if self.enable_hybrid:
                relevance = (self.dense_weight * d_score) + (self.bm25_weight * b_score)
            else:
                relevance = d_score

            meta = candidate["metadata"]
            doc_text = candidate["document"]

            # Extract pure content (strip contextual header if present)
            content = doc_text
            context_header = ""
            if doc_text.startswith("[ICMR STW:"):
                parts = doc_text.split("\n", 1)
                context_header = parts[0]
                content = parts[1] if len(parts) > 1 else ""

            evidence_obj = RetrievedEvidence(
                chunk_id=cid,
                stw_title=meta.get("stw_title", f"ICMR STW: {meta.get('disease', 'Clinical Guideline')}"),
                specialty=meta.get("specialty", "General Medicine"),
                disease=meta.get("disease", "Clinical Guideline"),
                page_number=int(meta.get("page_number", 1)),
                section_title=meta.get("section_title", "General Guidance"),
                section_type=meta.get("section_type", "GENERAL"),
                content=content.strip(),
                context_header=context_header,
                relevance_score=round(relevance, 4),
                dense_score=round(d_score, 4),
                bm25_score=round(b_score, 4),
                is_above_threshold=(relevance >= threshold),
                volume=meta.get("volume", "Volume 1"),
                source_url=meta.get("source_url", "https://www.icmr.gov.in/standard-treatment-workflows-stws"),
                metadata=meta
            )
            ranked_evidence.append(evidence_obj)

        # Sort descending by relevance score
        ranked_evidence.sort(key=lambda x: x.relevance_score, reverse=True)

        logger.info(
            f"Retrieved {len(ranked_evidence)} candidates for query '{query[:40]}...'. "
            f"Returning top {min(k, len(ranked_evidence))} (threshold: {threshold})"
        )

        return ranked_evidence[:k]
