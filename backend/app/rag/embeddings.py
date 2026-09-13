import logging
from typing import List, Union
import numpy as np

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Manages clinical text vector embedding generation using SentenceTransformers.
    """

    def __init__(self, model_name: str = None, device: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.device = device or settings.EMBEDDING_DEVICE
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model '{self.model_name}' on device '{self.device}'...")
            from sentence_transformers import SentenceTransformer
            try:
                self._model = SentenceTransformer(self.model_name, device=self.device, local_files_only=True)
            except Exception:
                self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def embed_text(self, text: str) -> List[float]:
        """Generates a normalized dense vector embedding for a single text."""
        embedding = self.model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return embedding.tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generates normalized dense vector embeddings for a list of texts."""
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """Returns embedding vector dimension."""
        return self.model.get_sentence_embedding_dimension()


class MockEmbeddingService:
    """
    Deterministic pseudo-embedding generator for fast isolated testing.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    def embed_text(self, text: str) -> List[float]:
        np.random.seed(abs(hash(text)) % (2**32))
        vec = np.random.randn(self._dimension)
        norm = np.linalg.norm(vec)
        return (vec / norm).tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dimension


# Global embedding service singleton
_embedding_instance = None


def get_embedding_service(use_mock: bool = False) -> Union[EmbeddingService, MockEmbeddingService]:
    global _embedding_instance
    if use_mock:
        return MockEmbeddingService()
    if _embedding_instance is None:
        _embedding_instance = EmbeddingService()
    return _embedding_instance
