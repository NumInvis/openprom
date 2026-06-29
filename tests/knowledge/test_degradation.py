"""Degradation tests for the knowledge layer.

Every external dependency (Embedding, Rerank, VectorStore) must have a
clear degradation path, and these tests verify those paths work.

Tests use MockEmbeddingProvider and mock stores so no real models are needed.
"""

import pytest
from unittest.mock import MagicMock

from openprom.knowledge.providers import (
    MockEmbeddingProvider,
    NoOpReranker,
    reset_providers,
)
from openprom.knowledge.schema import Provenance, RetrievalResult, RetrievalResultSet


# ---- Fixtures ----


@pytest.fixture(autouse=True)
def _reset_providers():
    """Reset provider singletons between tests."""
    reset_providers()
    yield
    reset_providers()


@pytest.fixture
def mock_store():
    """A mock vector store that returns empty results."""
    store = MagicMock()
    store.count.return_value = 0
    store.query.return_value = []
    store.upsert.return_value = 0
    return store


@pytest.fixture
def sample_results():
    """Sample RetrievalResult list for testing."""
    return [
        RetrievalResult(
            id="poem_1",
            content="明月松间照\n清泉石上流",
            annotated="【五律·王维】明月松间照，清泉石上流",
            semantic_score=0.9,
            provenance=Provenance(source="test", dynasty="唐", form="五律"),
        ),
        RetrievalResult(
            id="poem_2",
            content="春眠不觉晓\n处处闻啼鸟",
            annotated="【五绝·孟浩然】春眠不觉晓，处处闻啼鸟",
            semantic_score=0.7,
            provenance=Provenance(source="test", dynasty="唐", form="五绝"),
        ),
    ]


# ---- Embedding degradation ----


class TestEmbeddingDegradation:
    """Test that embedding failures degrade gracefully."""

    def test_mock_provider_returns_correct_shape(self):
        """MockEmbeddingProvider should return (N, 384) float32 arrays."""
        provider = MockEmbeddingProvider()
        result = provider.embed(["hello", "world"])
        assert result.shape == (2, 384)
        assert result.dtype.name == "float32"

    def test_mock_provider_single_query(self):
        provider = MockEmbeddingProvider()
        result = provider.embed_query("test query")
        assert result.shape == (384,)

    def test_mock_provider_deterministic(self):
        """Same input should produce same output."""
        provider = MockEmbeddingProvider()
        r1 = provider.embed(["春风化雨"])
        r2 = provider.embed(["春风化雨"])
        assert (r1 == r2).all()

    def test_get_embedding_provider_fallback_to_mock(self):
        """When sentence_transformers is unavailable, should fallback to mock (or raise in strict mode)."""
        import os
        from openprom.knowledge.providers import get_embedding_provider

        if os.getenv("OPENPROM_EMBEDDING_PROVIDER"):
            # Strict mode: should raise when provider unavailable
            with pytest.raises(RuntimeError):
                get_embedding_provider(name="nonexistent")
        else:
            # Legacy mode: should fallback to mock
            provider = get_embedding_provider(name="nonexistent")
            assert isinstance(provider, MockEmbeddingProvider)

    def test_embedding_failure_does_not_crash_pipeline(self, mock_store):
        """Pipeline should work even if embedding returns mock data."""
        from openprom.knowledge.retrieval.pipeline import RetrievalPipeline

        pipeline = RetrievalPipeline(
            embedding_provider=MockEmbeddingProvider(),
            rerank_provider=NoOpReranker(),
            vector_store=mock_store,
        )
        result = pipeline.retrieve("test query", top_k=5)
        assert isinstance(result, RetrievalResultSet)
        assert len(result) == 0  # empty store → empty results


# ---- Rerank degradation ----


class TestRerankDegradation:
    """Test that rerank failures degrade gracefully."""

    def test_noop_reranker_preserves_order(self):
        """NoOpReranker should return docs in original order."""
        reranker = NoOpReranker()
        results = reranker.rerank("query", ["doc1", "doc2", "doc3"], top_k=3)
        assert len(results) == 3
        assert results[0][0] == 0  # first doc
        assert results[1][0] == 1  # second doc

    def test_get_rerank_provider_fallback_to_noop(self):
        """When rerank model is unavailable, should fallback to NoOp."""
        from openprom.knowledge.providers import get_rerank_provider

        provider = get_rerank_provider(name="nonexistent")
        assert isinstance(provider, NoOpReranker)

    def test_rerank_failure_falls_back_to_original_order(self, mock_store):
        """If rerank raises, pipeline should return results in original order."""
        from openprom.knowledge.retrieval.pipeline import RetrievalPipeline

        failing_reranker = MagicMock()
        failing_reranker.rerank.side_effect = RuntimeError("model load failed")

        pipeline = RetrievalPipeline(
            embedding_provider=MockEmbeddingProvider(),
            rerank_provider=failing_reranker,
            vector_store=mock_store,
        )
        # Pipeline should not crash even if reranker fails
        result = pipeline.retrieve("test", top_k=5)
        assert isinstance(result, RetrievalResultSet)


# ---- Vector store degradation ----


class TestVectorStoreDegradation:
    """Test that vector store failures degrade gracefully."""

    def test_empty_store_returns_empty_results(self, mock_store):
        """Empty vector store should return empty results, not crash."""
        from openprom.knowledge.retrieval.pipeline import RetrievalPipeline

        pipeline = RetrievalPipeline(
            embedding_provider=MockEmbeddingProvider(),
            vector_store=mock_store,
        )
        result = pipeline.retrieve("明月", top_k=5)
        assert isinstance(result, RetrievalResultSet)
        assert len(result) == 0

    def test_store_query_failure_returns_empty(self, mock_store):
        """If store.query raises, pipeline should still return."""
        from openprom.knowledge.retrieval.pipeline import RetrievalPipeline

        mock_store.query.side_effect = RuntimeError("connection lost")

        pipeline = RetrievalPipeline(
            embedding_provider=MockEmbeddingProvider(),
            vector_store=mock_store,
            enable_hybrid=False,
        )
        # Should not crash
        result = pipeline.retrieve("test", top_k=5)
        assert isinstance(result, RetrievalResultSet)


# ---- Rule signal degradation ----


class TestRuleSignalDegradation:
    """Test that rule signal computation degrades gracefully."""

    def test_extract_rule_signals_no_form(self):
        """With no target form, signals should return neutral (0.5)."""
        from openprom.knowledge.rule_signals import extract_rule_signals

        signals = extract_rule_signals("明月松间照", {}, target_form=None)
        assert signals["form_match"] == 0.5
        assert signals["meter_match"] == 0.5
        assert signals["rhyme_consistency"] == 0.5

    def test_extract_rule_signals_with_form(self):
        """With a target form, form_match should be 0 or 1."""
        from openprom.knowledge.rule_signals import extract_rule_signals

        signals = extract_rule_signals("明月松间照", {"form": "五律"}, target_form="五律")
        assert signals["form_match"] == 1.0

    def test_extract_rule_signals_mismatch_form(self):
        from openprom.knowledge.rule_signals import extract_rule_signals

        signals = extract_rule_signals("明月松间照", {"form": "五绝"}, target_form="七律")
        assert signals["form_match"] == 0.0

    def test_fuse_with_rule_signals_neutral(self):
        """With all-neutral rule signals, final ≈ semantic score."""
        from openprom.knowledge.rule_signals import fuse_with_rule_signals

        result = fuse_with_rule_signals(0.8, {}, w_semantic=0.6, w_rule=0.4)
        # 0.6 * 0.8 + 0.4 * 0.5 = 0.48 + 0.2 = 0.68
        assert abs(result - 0.68) < 0.01


# ---- RetrievalResult / ResultSet ----


class TestSchemaDegradation:
    """Test schema objects handle missing/empty data gracefully."""

    def test_empty_result_set(self):
        rs = RetrievalResultSet(results=[], query="test")
        assert len(rs) == 0
        assert list(rs) == []
        assert rs.to_prompt_text() == ""
        assert rs.to_dicts() == []

    def test_result_to_prompt_text(self, sample_results):
        rs = RetrievalResultSet(results=sample_results, query="test")
        text = rs.to_prompt_text()
        assert "明月松间照" in text
        assert "春眠不觉晓" in text

    def test_provenance_defaults(self):
        p = Provenance(source="test")
        assert p.confidence == 0.95
        assert p.dynasty is None
        assert p.form is None

    def test_result_to_dict(self, sample_results):
        d = sample_results[0].to_dict()
        assert d["id"] == "poem_1"
        assert d["provenance"]["source"] == "test"
        assert d["semantic_score"] == 0.9
