"""Embedding providers for the poetry RAG layer.

Supports local sentence-transformers models. API-based embeddings can be
added here later if the LLM gateway exposes an embedding endpoint.
"""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Base embedding provider."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class SentenceTransformerProvider(EmbeddingProvider):
    """Local sentence-transformers provider (e.g. BAAI/bge-small-zh-v1.5)."""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model {self.model_name} on {self.device}")
            self._model = SentenceTransformer(self.model_name, device=self.device)
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def embed(self, texts: List[str]) -> List[List[float]]:
        self._load_model()
        # bge models benefit from a short prefix for retrieval tasks
        prefixed = [f"{t}" for t in texts]
        embeddings = self._model.encode(prefixed, normalize_embeddings=True)
        return embeddings.tolist()


class MockEmbeddingProvider(EmbeddingProvider):
    """Fallback provider that returns deterministic pseudo-embeddings.

    Useful when no embedding model is available; not recommended for production.
    """

    def embed(self, texts: List[str]) -> List[List[float]]:
        import hashlib

        results = []
        for text in texts:
            h = hashlib.md5(text.encode("utf-8")).digest()
            vec = [((b / 255.0) - 0.5) * 2 for b in h]
            # extend to 384 dims deterministically
            vec = (vec * 13)[:384]
            # normalize
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            vec = [x / norm for x in vec]
            results.append(vec)
        return results


def get_embedding_provider() -> EmbeddingProvider:
    """Factory: returns the configured embedding provider."""
    provider_type = os.getenv("OPENPROM_EMBEDDING_PROVIDER", "sentence_transformers").lower()
    if provider_type == "mock":
        return MockEmbeddingProvider()

    model = os.getenv("OPENPROM_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    device = os.getenv("OPENPROM_EMBEDDING_DEVICE", "cpu")
    return SentenceTransformerProvider(model_name=model, device=device)
