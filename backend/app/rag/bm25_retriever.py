import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Plus, BM25Okapi

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


CLINICAL_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}


def tokenize_clinical_text(text: str) -> List[str]:
    """
    Tokenizes clinical queries and text into lowercase alphanumeric tokens,
    stripping common stopwords while preserving acronyms (AKI, STEMI, ECG)
    and pharmaceutical names.
    """
    if not text:
        return []
    # Alphanumeric tokens with hyphens or slashes
    tokens = re.findall(r"\b[a-zA-Z0-9\-\./]+\b", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in CLINICAL_STOPWORDS]


class BM25ClinicalRetriever:
    """
    BM25 lexical keyword retriever for exact medical terminology,
    abbreviations, and medication name matching in ICMR STWs.
    """

    def __init__(self, chunks_path: Optional[Path] = None):
        self.chunks_path = Path(chunks_path or (settings.DATA_PROCESSED_DIR / "icmr_clinical_chunks.json"))
        self.chunks: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Plus] = None
        self._initialize_index()

    def _initialize_index(self) -> None:
        """Loads chunks and initializes the BM25Plus index."""
        if not self.chunks_path.exists():
            logger.warning(f"BM25 index source not found at {self.chunks_path}. BM25 search will be empty.")
            self.chunks = []
            self.bm25 = None
            return

        try:
            with open(self.chunks_path, "r", encoding="utf-8") as f:
                self.chunks = json.load(f)

            corpus = [tokenize_clinical_text(c.get("full_chunk_text", c.get("content", ""))) for c in self.chunks]
            self.bm25 = BM25Plus(corpus)
            logger.info(f"Initialized BM25 index with {len(self.chunks)} clinical chunks.")
        except Exception as e:
            logger.error(f"Failed to initialize BM25 index: {e}")
            self.bm25 = None

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes BM25 keyword search, normalizes scores into [0, 1],
        and applies metadata filters.
        """
        if not self.bm25 or not self.chunks:
            return []

        tokens = tokenize_clinical_text(query)
        if not tokens:
            return []

        raw_scores = self.bm25.get_scores(tokens)
        max_score = max(raw_scores) if len(raw_scores) > 0 and max(raw_scores) > 0 else 1.0

        candidates = []
        for idx, score in enumerate(raw_scores):
            if score <= 0:
                continue

            chunk = self.chunks[idx]
            # Apply metadata filtering if specified
            if where:
                match = True
                meta = chunk.get("metadata", chunk)
                flat_filters = {}
                if "$and" in where and isinstance(where["$and"], list):
                    for cond in where["$and"]:
                        flat_filters.update(cond)
                else:
                    flat_filters = where

                for key, val in flat_filters.items():
                    if meta.get(key) != val and chunk.get(key) != val:
                        match = False
                        break
                if not match:
                    continue

            norm_score = float(score / max_score)
            candidates.append({
                "chunk_id": chunk["chunk_id"],
                "document": chunk.get("full_chunk_text", chunk.get("content", "")),
                "metadata": chunk.get("metadata", chunk),
                "bm25_score": round(norm_score, 4),
                "raw_bm25_score": round(float(score), 4)
            })

        # Sort descending by normalized BM25 score
        candidates.sort(key=lambda x: x["bm25_score"], reverse=True)
        return candidates[:top_k]
