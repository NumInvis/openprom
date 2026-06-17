"""Smoke tests for knowledge metrics helpers."""

from openprom.knowledge.metrics import (
    get_metrics_text,
    record_cache_hit,
    record_rerank,
    record_retrieval,
)


class TestRecordRetrieval:
    def test_call_does_not_raise(self):
        record_retrieval("dense", latency=0.05, result_count=10)
        record_retrieval("bm25", latency=0.02, result_count=3, status="error")

    def test_with_hybrid_query_type(self):
        record_retrieval("hybrid", latency=0.1, result_count=5, status="success")


class TestRecordRerank:
    def test_hit(self):
        record_rerank(hit=True)

    def test_miss(self):
        record_rerank(hit=False)


class TestRecordCacheHit:
    def test_embedding_cache(self):
        record_cache_hit("embedding")

    def test_rerank_cache(self):
        record_cache_hit("rerank")

    def test_retrieval_cache(self):
        record_cache_hit("retrieval")


class TestGetMetricsText:
    def test_returns_str_or_none(self):
        result = get_metrics_text()
        assert result is None or isinstance(result, str)
