"""Knowledge layer router: search and inspect the retrieval pipeline.

Exposes the knowledge layer (`openprom.knowledge`) as HTTP endpoints so the
RAG layer is no longer a black box. Useful for debugging, demo and ops.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from openprom.routers.common import (
    KnowledgeSearchHit,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
    PormErrorCode,
    PormHTTPException,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["知识层"])


@router.post("/search", response_model=KnowledgeSearchResponse, summary="知识层检索")
async def knowledge_search(request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    """Run the knowledge layer retrieval pipeline.

    Returns structured results with provenance, scores, and rule signals.
    Use `task_type` to apply task-aware retrieval profiles.
    """
    try:
        from openprom.knowledge.retrieval.pipeline import get_retrieval_pipeline
        pipeline = get_retrieval_pipeline()
    except Exception as e:
        raise PormHTTPException(
            status_code=503,
            error_code=PormErrorCode.INTERNAL_ERROR,
            detail=f"Knowledge layer unavailable: {e}",
        )

    t0 = time.time()
    try:
        result_set = pipeline.retrieve(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
            target_form=request.target_form,
            task_type=request.task_type,
        )
    except Exception as e:
        logger.exception("Knowledge search failed")
        raise PormHTTPException(
            status_code=500,
            error_code=PormErrorCode.INTERNAL_ERROR,
            detail=f"Retrieval failed: {e}",
        )
    latency_ms = (time.time() - t0) * 1000.0

    hits = [
        KnowledgeSearchHit(
            id=r.id,
            content=r.content,
            annotated=r.annotated,
            chunk_type=r.chunk_type,
            final_score=r.final_score,
            semantic_score=r.semantic_score,
            rerank_score=r.rerank_score,
            rule_signals=r.rule_signals or {},
            provenance=r.provenance.to_dict() if r.provenance else {},
            metadata=r.metadata or {},
        )
        for r in result_set.results
    ]

    return KnowledgeSearchResponse(
        query=result_set.query,
        total_candidates=result_set.total_candidates,
        pipeline_stages=result_set.pipeline_stages,
        results=hits,
        latency_ms=round(latency_ms, 2),
    )


@router.get("/stats", response_model=KnowledgeStatsResponse, summary="知识层运行状态")
async def knowledge_stats() -> KnowledgeStatsResponse:
    """Inspect knowledge layer state: vector store size, cache stats, providers, skills."""
    from openprom.infrastructure.config.settings import get_settings
    settings = get_settings()
    features = getattr(settings, "features", None)
    knowledge_cfg = getattr(settings, "knowledge", None)

    knowledge_v2 = bool(features and getattr(features, "knowledge_layer_v2", False))
    knowledge_enabled = bool(knowledge_cfg and getattr(knowledge_cfg, "enabled", False))

    vector_size = 0
    embedding_provider = "unknown"
    rerank_provider = "unknown"
    retrieval_stats: dict = {}
    rerank_stats: dict = {}
    skills: list = []

    try:
        from openprom.knowledge.providers.vector_store import get_vector_store
        store = get_vector_store()
        vector_size = store.count()
    except Exception as e:
        logger.debug("Vector store size unavailable: %s", e)

    try:
        from openprom.knowledge.providers import get_embedding_provider, get_rerank_provider
        embedding_provider = getattr(get_embedding_provider(), "name", "unknown")
        rerank_provider = getattr(get_rerank_provider(), "name", "unknown")
    except Exception as e:
        logger.debug("Provider info unavailable: %s", e)

    try:
        from openprom.knowledge.memory.cache import get_retrieval_cache, get_rerank_cache
        retrieval_stats = get_retrieval_cache().stats()
        rerank_stats = get_rerank_cache().stats()
    except Exception as e:
        logger.debug("Cache stats unavailable: %s", e)

    try:
        from openprom.knowledge.skills.classic import get_knowledge_skills
        skills = list(get_knowledge_skills().keys())
    except Exception as e:
        logger.debug("Skills list unavailable: %s", e)

    return KnowledgeStatsResponse(
        enabled=knowledge_enabled,
        knowledge_layer_v2=knowledge_v2,
        vector_store_size=vector_size,
        retrieval_cache=retrieval_stats,
        rerank_cache=rerank_stats,
        embedding_provider=embedding_provider,
        rerank_provider=rerank_provider,
        skills=skills,
    )
