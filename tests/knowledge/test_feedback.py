"""Tests for FeedbackIngestor with mocked dependencies."""

import pytest
from unittest.mock import MagicMock, patch

from openprom.knowledge.memory.feedback import FeedbackIngestor


class TestFeedbackIngestor:
    @pytest.fixture()
    def ingestor(self):
        return FeedbackIngestor(min_score=75)

    @pytest.fixture()
    def mock_meter_tool(self):
        with patch(
            "openprom.knowledge.memory.feedback.check_meter"
        ) as mock_check_meter:
            yield mock_check_meter

    @pytest.fixture()
    def mock_store_and_embed(self):
        with patch(
            "openprom.knowledge.memory.feedback.get_vector_store"
        ) as mock_get_store, patch(
            "openprom.knowledge.providers.get_embedding_provider"
        ) as mock_get_embed:
            store = MagicMock()
            mock_get_store.return_value = store

            embedder = MagicMock()
            embedder.embed.return_value = [[0.1] * 8]
            mock_get_embed.return_value = embedder

            yield store, embedder

    def test_low_score_rejected(self, ingestor, mock_meter_tool, mock_store_and_embed):
        mock_meter_tool.return_value = {"is_compliant": True}
        store, _ = mock_store_and_embed

        result = ingestor.ingest(
            content="春眠不觉晓",
            score=50.0,
            meter_type="couplet",
        )
        assert result is None
        store.upsert.assert_not_called()

    def test_non_compliant_rejected(self, ingestor, mock_meter_tool, mock_store_and_embed):
        mock_meter_tool.return_value = {
            "is_compliant": False,
            "violations": ["tone error at position 3"],
        }
        store, _ = mock_store_and_embed

        result = ingestor.ingest(
            content="乱七八糟的内容",
            score=90.0,
            meter_type="couplet",
        )
        assert result is None
        store.upsert.assert_not_called()

    def test_passing_content_gets_provenance(
        self, ingestor, mock_meter_tool, mock_store_and_embed
    ):
        mock_meter_tool.return_value = {"is_compliant": True}
        store, embedder = mock_store_and_embed

        result = ingestor.ingest(
            content="明月松间照",
            metadata={"author": "王维"},
            score=85.0,
            meter_type="couplet",
        )

        assert result is not None
        assert result.provenance.source == "user_feedback"
        assert result.provenance.confidence == 0.5
        assert result.metadata["user_score"] == 85.0
        assert result.metadata["meter_type"] == "couplet"
        assert result.metadata["author"] == "王维"
        assert result.chunk_type == "couplet"

        store.upsert.assert_called_once()
        call_kw = store.upsert.call_args
        assert call_kw.kwargs["metadatas"][0]["source"] == "user_feedback"
        assert call_kw.kwargs["metadatas"][0]["confidence"] == 0.5

    def test_passing_ci_meter_type(self, ingestor, mock_meter_tool, mock_store_and_embed):
        mock_meter_tool.return_value = {"is_compliant": True}

        result = ingestor.ingest(
            content="明月几时有",
            score=90.0,
            meter_type="ci",
        )
        assert result is not None
        assert result.chunk_type == "ci"

    def test_unknown_meter_type_defaults_to_poem(
        self, ingestor, mock_meter_tool, mock_store_and_embed
    ):
        mock_meter_tool.return_value = {"is_compliant": True}

        result = ingestor.ingest(
            content="some content",
            score=90.0,
            meter_type="unknown",
        )
        assert result is not None
        assert result.chunk_type == "poem"

    def test_min_score_threshold_exactly(self, ingestor, mock_meter_tool, mock_store_and_embed):
        mock_meter_tool.return_value = {"is_compliant": True}

        result = ingestor.ingest(content="test", score=75.0, meter_type="couplet")
        assert result is not None
