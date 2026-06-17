"""Prometheus metrics for the knowledge layer.

Exposes counters, histograms, and gauges for retrieval, reranking, caching,
embedding, and vector-store operations.  Falls back to no-op stubs when
prometheus_client is not installed so the rest of the code can call record_*
helpers unconditionally.
"""

from __future__ import annotations

from typing import Optional

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Metric definitions (only when prometheus_client is present)
# ---------------------------------------------------------------------------

if PROMETHEUS_AVAILABLE:
    KNOWLEDGE_RETRIEVAL_TOTAL = Counter(
        "porm_knowledge_retrieval_total",
        "Total knowledge retrieval calls",
        ["query_type", "status"],
    )
    KNOWLEDGE_RETRIEVAL_LATENCY_SECONDS = Histogram(
        "porm_knowledge_retrieval_latency_seconds",
        "Knowledge retrieval latency in seconds",
        ["query_type"],
    )
    KNOWLEDGE_RERANK_TOTAL = Counter(
        "porm_knowledge_rerank_total",
        "Total rerank calls",
        ["result"],
    )
    KNOWLEDGE_CACHE_HITS_TOTAL = Counter(
        "porm_knowledge_cache_hits_total",
        "Total knowledge cache hits",
        ["cache_type"],
    )
    KNOWLEDGE_EMBEDDING_CALLS_TOTAL = Counter(
        "porm_knowledge_embedding_calls_total",
        "Total embedding model calls",
    )
    KNOWLEDGE_VECTOR_STORE_SIZE = Gauge(
        "porm_knowledge_vector_store_size",
        "Current number of vectors in the knowledge store",
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def record_retrieval(
    query_type: str,
    latency: float,
    result_count: int,
    *,
    status: str = "success",
) -> None:
    """Record a completed retrieval call.

    Parameters
    ----------
    query_type:
        Kind of query (e.g. "dense", "bm25", "hybrid").
    latency:
        Wall-clock seconds the retrieval took.
    result_count:
        Number of results returned (logged via histogram bucket is not needed;
        the counter tracks call volume).
    status:
        Outcome label – ``"success"`` or ``"error"``.
    """
    if not PROMETHEUS_AVAILABLE:
        return
    KNOWLEDGE_RETRIEVAL_TOTAL.labels(query_type=query_type, status=status).inc()
    KNOWLEDGE_RETRIEVAL_LATENCY_SECONDS.labels(query_type=query_type).observe(latency)


def record_rerank(hit: bool) -> None:
    """Record a rerank cache/event.

    Parameters
    ----------
    hit:
        ``True`` when the reranker produced a hit, ``False`` for a miss.
    """
    if not PROMETHEUS_AVAILABLE:
        return
    KNOWLEDGE_RERANK_TOTAL.labels(result="hit" if hit else "miss").inc()


def record_cache_hit(cache_type: str) -> None:
    """Record a knowledge-layer cache hit.

    Parameters
    ----------
    cache_type:
        Identifier for the cache (e.g. ``"embedding"``, ``"rerank"``, ``"retrieval"``).
    """
    if not PROMETHEUS_AVAILABLE:
        return
    KNOWLEDGE_CACHE_HITS_TOTAL.labels(cache_type=cache_type).inc()


def record_embedding_call() -> None:
    """Record a single embedding-model invocation."""
    if not PROMETHEUS_AVAILABLE:
        return
    KNOWLEDGE_EMBEDDING_CALLS_TOTAL.inc()


def set_vector_store_size(size: int) -> None:
    """Update the vector-store size gauge."""
    if not PROMETHEUS_AVAILABLE:
        return
    KNOWLEDGE_VECTOR_STORE_SIZE.set(size)


def get_metrics_text() -> Optional[str]:
    """Return Prometheus text-format metrics, or ``None`` if unavailable."""
    if not PROMETHEUS_AVAILABLE:
        return None
    return generate_latest().decode("utf-8")
