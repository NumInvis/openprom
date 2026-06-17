"""Rerank provider implementations.

Factory: get_rerank_factory tries onnx → sentence_transformers → noop.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_rerank_factory(name: Optional[str] = None):
    """Return a RerankProvider instance.

    Fallback chain:
      1. ONNX runtime provider (onnx)
      2. Sentence-Transformers CrossEncoder (sentence_transformers)
      3. NoOp pass-through (noop)
    """
    if name is None:
        name = os.getenv("OPENPROM_RERANK_PROVIDER", "noop")

    if name in ("onnx", "bge-reranker-v2-m3", "bge-reranker-base"):
        try:
            from openprom.knowledge.providers.rerank.onnx_provider import (
                OnnxRerankProvider,
            )

            provider = OnnxRerankProvider(model_name=name if name != "onnx" else None)
            provider._load()
            return provider
        except Exception as exc:
            logger.warning("ONNX rerank provider failed, falling back: %s", exc)

    if name in ("sentence_transformers", "st"):
        try:
            from openprom.knowledge.providers.rerank.sentence_transformer_provider import (
                SentenceTransformerRerankProvider,
            )

            provider = SentenceTransformerRerankProvider()
            provider._load()
            return provider
        except Exception as exc:
            logger.warning(
                "SentenceTransformer rerank provider failed, falling back: %s", exc
            )

    from openprom.knowledge.providers import NoOpReranker

    return NoOpReranker()
