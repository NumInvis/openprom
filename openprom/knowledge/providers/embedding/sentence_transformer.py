"""Sentence-transformers embedding provider.

Wraps the existing SentenceTransformerProvider from services/rag/embeddings.py
into the knowledge layer protocol.
"""

from __future__ import annotations

import logging
import os
from typing import List

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedding:
    """Local sentence-transformers provider (e.g. BAAI/bge-small-zh-v1.5)."""

    name = "sentence_transformers"

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        dim: int = 512,
    ):
        self.model_name = model_name or os.getenv(
            "OPENPROM_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"
        )
        self.device = device or os.getenv("OPENPROM_EMBEDDING_DEVICE", "cpu")
        self.dim = dim
        self._model = None
        # Eagerly attempt to load the model so factory-level fallback to
        # MockEmbeddingProvider can happen before any retrieval call.
        self._load_model()

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model {self.model_name} on {self.device}")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            # Update dim from loaded model
            try:
                self.dim = self._model.get_sentence_embedding_dimension()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def embed(self, texts: List[str]) -> NDArray[np.float32]:
        self._load_model()
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return np.array(embeddings, dtype=np.float32)

    def embed_query(self, query: str) -> NDArray[np.float32]:
        return self.embed([query])[0]
