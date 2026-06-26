"""Feedback ingestion: high-scoring user couplets/poems → knowledge base.

When a user produces content that passes meter check and meets the score
threshold, it gets embedded and upserted into the vector store with
provenance=user_feedback so future retrieval can surface it.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from openprom.infrastructure.config.settings import get_settings
from openprom.knowledge.providers.vector_store import get_vector_store
from openprom.knowledge.schema import Provenance, RetrievalResult
from openprom.services.meter_tool import check_meter

logger = logging.getLogger(__name__)

_global_ingestor: Optional["FeedbackIngestor"] = None


class FeedbackIngestor:
    """Ingests high-scoring user-generated poetry into the knowledge base.

    Gate 1: content must pass check_meter.
    Gate 2: score must be >= min_score threshold.
    """

    def __init__(self, min_score: int = 75):
        self.min_score = min_score

    def ingest(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        score: float = 0.0,
        meter_type: str = "couplet",
    ) -> Optional[RetrievalResult]:
        """Attempt to ingest user feedback into the vector store.

        Args:
            content: The poem/couplet text.
            metadata: Additional metadata (title, author, tags, etc.).
            score: Quality score (0–100) assigned by the scorer.
            meter_type: One of 'couplet', 'shi', 'ci'.

        Returns:
            The upserted RetrievalResult on success, None if gated out.
        """
        # Gate 1: meter check
        meter_result = check_meter(content, meter_type=meter_type)
        if not meter_result.get("is_compliant", False):
            violations = meter_result.get("violations", [])
            logger.info(
                "Feedback rejected by meter check: %s | violations=%s",
                content[:40],
                violations,
            )
            return None

        # Gate 2: score threshold
        if score < self.min_score:
            logger.info(
                "Feedback rejected by score gate: %.1f < %d | content=%s",
                score,
                self.min_score,
                content[:40],
            )
            return None

        # Build RetrievalResult
        meta = dict(metadata) if metadata else {}
        meta["user_score"] = score
        meta["meter_type"] = meter_type

        provenance = Provenance(source="user_feedback", confidence=0.5)
        result_id = f"uf_{uuid.uuid4().hex[:12]}"

        retrieval_result = RetrievalResult(
            id=result_id,
            content=content,
            annotated=content,
            provenance=provenance,
            chunk_type=meter_type if meter_type in ("couplet", "shi", "ci") else "poem",
            metadata=meta,
        )

        # Embed and upsert into vector store
        from openprom.knowledge.providers import get_embedding_provider

        embedding_provider = get_embedding_provider()
        embedding = embedding_provider.embed([content])
        store = get_vector_store()

        store_meta = {
            "source": "user_feedback",
            "confidence": 0.5,
            "chunk_type": retrieval_result.chunk_type,
            **{k: str(v) for k, v in meta.items()},
        }

        store.upsert(
            ids=[result_id],
            embeddings=embedding,
            metadatas=[store_meta],
            documents=[content],
        )

        logger.info(
            "Feedback ingested: id=%s score=%.1f content=%s", result_id, score, content[:40]
        )
        return retrieval_result


def get_feedback_ingestor() -> FeedbackIngestor:
    """Factory: get or create the singleton FeedbackIngestor."""
    global _global_ingestor
    if _global_ingestor is not None:
        return _global_ingestor

    settings = get_settings()
    min_score = settings.knowledge.memory.min_score
    _global_ingestor = FeedbackIngestor(min_score=min_score)
    return _global_ingestor
