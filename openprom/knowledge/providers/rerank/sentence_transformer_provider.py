"""Sentence-Transformers cross-encoder rerank provider.

Uses sentence_transformers.CrossEncoder for reranking.
Supports models like BAAI/bge-reranker-v2-m3 directly via HuggingFace.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"


class SentenceTransformerRerankProvider:
    """Cross-encoder reranker using sentence_transformers.CrossEncoder."""

    name = "sentence_transformers-rerank"

    def __init__(
        self,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
        max_length: int = 512,
    ):
        self.model_name = model_name or os.getenv(
            "OPENPROM_RERANK_MODEL", _DEFAULT_MODEL
        )
        self.model_path = model_path
        self.max_length = max_length
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return

        from sentence_transformers import CrossEncoder

        model_dir = self.model_path or self.model_name
        logger.info("Loading CrossEncoder rerank model from %s", model_dir)
        self._model = CrossEncoder(model_dir, max_length=self.max_length)
        logger.info("CrossEncoder rerank model loaded: %s", model_dir)

    def rerank(
        self, query: str, docs: List[str], top_k: int = 10
    ) -> List[Tuple[int, float]]:
        """Rerank docs against query using CrossEncoder scoring.

        Returns list of (original_index, score) sorted by score descending,
        length <= top_k.
        """
        self._load()

        if not docs:
            return []

        pairs = [(query, doc) for doc in docs]
        raw_scores = self._model.predict(pairs)

        scores = [(i, float(s)) for i, s in enumerate(raw_scores)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
