"""Retrieval cache: TTL-based in-memory cache for retrieval results.

Reduces latency and cost by caching query → result mappings.
Also provides RerankCache for caching cross-encoder rerank scores.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

from openprom.knowledge.schema import RetrievalResultSet

logger = logging.getLogger(__name__)


class RetrievalCache:
    """Thread-safe TTL cache for retrieval results."""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 500):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: dict[str, tuple[float, RetrievalResultSet]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(query: str, top_k: int, filters: Optional[dict] = None) -> str:
        raw = f"{query}|{top_k}|{filters or {}}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(
        self, query: str, top_k: int, filters: Optional[dict] = None
    ) -> Optional[RetrievalResultSet]:
        key = self._make_key(query, top_k, filters)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            ts, result = entry
            if time.time() - ts > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None
            self._hits += 1
            return result

    def put(
        self,
        query: str,
        top_k: int,
        result: RetrievalResultSet,
        filters: Optional[dict] = None,
    ) -> None:
        key = self._make_key(query, top_k, filters)
        with self._lock:
            if len(self._cache) >= self.max_size:
                oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]
            self._cache[key] = (time.time(), result)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "ttl_seconds": self.ttl_seconds,
            }


class RerankCache:
    """Thread-safe TTL cache for rerank scores.

    Caches (query, doc_id_list) → rerank_scores to avoid re-running
    the expensive cross-encoder on the same inputs.
    """

    def __init__(self, ttl_seconds: int = 1800, max_size: int = 200):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, Tuple[float, List[Tuple[int, float]]]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(query: str, doc_ids: List[str]) -> str:
        ids_str = "|".join(doc_ids)
        raw = f"{query}||{ids_str}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, query: str, doc_ids: List[str]) -> Optional[List[Tuple[int, float]]]:
        key = self._make_key(query, doc_ids)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            ts, scores = entry
            if time.time() - ts > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None
            self._hits += 1
            return scores

    def put(self, query: str, doc_ids: List[str], scores: List[Tuple[int, float]]) -> None:
        key = self._make_key(query, doc_ids)
        with self._lock:
            if len(self._cache) >= self.max_size:
                oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]
            self._cache[key] = (time.time(), scores)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "ttl_seconds": self.ttl_seconds,
            }


_global_cache: Optional[RetrievalCache] = None
_global_rerank_cache: Optional[RerankCache] = None


def get_retrieval_cache(ttl_seconds: int = 3600) -> RetrievalCache:
    global _global_cache
    if _global_cache is None:
        _global_cache = RetrievalCache(ttl_seconds=ttl_seconds)
    return _global_cache


def get_rerank_cache(ttl_seconds: int = 1800) -> RerankCache:
    global _global_rerank_cache
    if _global_rerank_cache is None:
        _global_rerank_cache = RerankCache(ttl_seconds=ttl_seconds)
    return _global_rerank_cache
