"""Provider base protocols and the provider registry.

All providers follow the same pattern: Protocol definition → multiple implementations
→ factory function with fallback chain. This ensures models are swappable at runtime
and failures degrade gracefully.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, Tuple, runtime_checkable

import numpy as np
from numpy.typing import NDArray


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Embeds text into dense vectors."""

    name: str
    dim: int

    def embed(self, texts: List[str]) -> NDArray[np.float32]:
        """Embed a batch of texts. Returns (N, dim) float32 array."""
        ...

    def embed_query(self, query: str) -> NDArray[np.float32]:
        """Embed a single query. May apply query-specific prefix/stipulation."""
        ...


@runtime_checkable
class RerankProvider(Protocol):
    """Cross-encoder reranker that scores query-document relevance."""

    name: str

    def rerank(self, query: str, docs: List[str], top_k: int = 10) -> List[Tuple[int, float]]:
        """Rerank docs against query.

        Returns: list of (original_index, score) sorted by score desc, length <= top_k.
        """
        ...


class NoOpReranker:
    """Pass-through reranker that returns docs in original order."""

    name = "noop"

    def rerank(self, query: str, docs: List[str], top_k: int = 10) -> List[Tuple[int, float]]:
        return [(i, 1.0 - i * 0.01) for i in range(min(top_k, len(docs)))]


class MockEmbeddingProvider:
    """Deterministic hash-based embeddings for testing/fallback."""

    name = "mock"
    dim = 384

    def embed(self, texts: List[str]) -> NDArray[np.float32]:
        import hashlib

        results = []
        for text in texts:
            h = hashlib.md5(text.encode("utf-8")).digest()
            vec = [((b / 255.0) - 0.5) * 2 for b in h]
            # Extend to target dim by cycling
            extended = []
            while len(extended) < self.dim:
                extended.extend(vec)
            vec = extended[: self.dim]
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            vec = [x / norm for x in vec]
            results.append(vec)
        return np.array(results, dtype=np.float32)

    def embed_query(self, query: str) -> NDArray[np.float32]:
        return self.embed([query])[0]


# ---- Provider Registry (singleton factories with fallback chains) ----

_embedding_provider: Optional[EmbeddingProvider] = None
_rerank_provider: Optional[RerankProvider] = None


def get_embedding_provider(name: Optional[str] = None) -> EmbeddingProvider:
    """Get or create the singleton embedding provider.

    Fallback chain: requested → sentence_transformers → mock.
    """
    global _embedding_provider
    if _embedding_provider is not None and (name is None or _embedding_provider.name == name):
        return _embedding_provider

    # Try requested or configured provider
    if name is None:
        import os

        name = os.getenv("OPENPROM_EMBEDDING_PROVIDER", "sentence_transformers")

    if name == "sentence_transformers":
        try:
            from openprom.knowledge.providers.embedding.sentence_transformer import (
                SentenceTransformerEmbedding,
            )

            _embedding_provider = SentenceTransformerEmbedding()
            return _embedding_provider
        except Exception:
            pass

    if name == "onnx":
        try:
            from openprom.knowledge.providers.embedding.onnx_provider import (
                OnnxEmbeddingProvider,
            )

            _embedding_provider = OnnxEmbeddingProvider()
            return _embedding_provider
        except Exception:
            pass

    # Fallback
    _embedding_provider = MockEmbeddingProvider()
    return _embedding_provider


def get_rerank_provider(name: Optional[str] = None) -> RerankProvider:
    """Get or create the singleton rerank provider.

    Fallback chain: requested → onnx → sentence_transformers → noop.
    """
    global _rerank_provider
    if _rerank_provider is not None and (name is None or _rerank_provider.name == name):
        return _rerank_provider

    from openprom.knowledge.providers.rerank import get_rerank_factory

    _rerank_provider = get_rerank_factory(name)
    return _rerank_provider


def reset_providers() -> None:
    """Reset singleton state (for testing)."""
    global _embedding_provider, _rerank_provider
    _embedding_provider = None
    _rerank_provider = None
