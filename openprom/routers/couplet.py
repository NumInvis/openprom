"""Couplet scoring / generation / completion router."""

import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse, JSONResponse

from openprom.routers.common import (
    CoupletRequest, CoupletResponse, GenerateRequest, GenerateResponse,
    PormHTTPException, PormErrorCode, get_scorer
)
from openprom.services.couplet_generator import CoupletGenerator
from openprom.infrastructure.cache import get_cache_service
from openprom.infrastructure.database import get_db_manager
from openprom.infrastructure.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/couplet", tags=["对联"])


def _build_response(score: Any, processing_time_ms: float) -> Dict[str, Any]:
    return {
        "upper": score.upper,
        "lower": score.lower,
        "formal_score": score.formal_score,
        "technique_score": score.technique_score,
        "artistic_score": score.artistic_score,
        "impression_score": score.impression_score,
        "total_score": score.total_score,
        "grade": score.grade,
        "pingze_score": score.pingze_score,
        "warnings": score.warnings,
        "comments": score.comments,
        "processing_time_ms": processing_time_ms,
        "detail": {
            "word_analysis": score.word_analysis,
            "pingze_upper": score.pingze_score,
            "pingze_lower": score.pingze_score,
        },
    }


def _generate_stream(upper: str, lower: str, scorer: Any):
    """Yield SSE events during scoring."""
    import json
    start = time.time()
    yield f"data: {json.dumps({'event': 'start', 'upper': upper, 'lower': lower}, ensure_ascii=False)}\n\n"
    try:
        score = scorer.analyze(upper, lower)
        payload = _build_response(score, round((time.time() - start) * 1000, 2))
        payload["event"] = "result"
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.exception("Couplet scoring stream failed")
        yield f"data: {json.dumps({'event': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


@router.post("/analyze", response_model=CoupletResponse)
async def couplet_analyze(
    request: Request,
    req: CoupletRequest,
    x_session_id: str = Header(default=None, alias="X-Session-ID"),
    scorer: Any = Depends(get_scorer),
):
    """Score a couplet."""
    start = time.time()

    if req.stream:
        return StreamingResponse(
            _generate_stream(req.upper, req.lower, scorer),
            media_type="text/event-stream",
        )

    cache = get_cache_service()
    cache_prefix = "couplet"
    import hashlib
    cache_key_raw = hashlib.md5(f"{req.upper}|{req.lower}".encode("utf-8")).hexdigest()
    if req.enable_cache:
        cached = cache.get(cache_prefix, cache_key_raw)
        if cached:
            cached["cached"] = True
            return JSONResponse(content=cached)

    if len(req.upper) != len(req.lower):
        raise PormHTTPException(400, PormErrorCode.LENGTH_MISMATCH, "上下联字数不等")

    score = scorer.analyze(req.upper, req.lower)
    response = _build_response(score, round((time.time() - start) * 1000, 2))
    response["cached"] = False
    response["session_id"] = x_session_id or str(uuid.uuid4())

    try:
        db = get_db_manager()
        record = db.save_couplet_analysis(score)
        response["id"] = record.id if hasattr(record, "id") else None
    except Exception as e:
        logger.warning(f"Failed to persist analysis: {e}")

    if req.enable_cache:
        try:
            from datetime import timedelta
            cache.set(cache_prefix, cache_key_raw, response, ttl=timedelta(seconds=3600))
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

    return JSONResponse(content=response)


@router.post("/generate", response_model=GenerateResponse)
async def couplet_generate(request: Request, req: GenerateRequest):
    """Generate a couplet from a prompt."""
    generator = CoupletGenerator()
    if req.stream:
        return StreamingResponse(
            generator.generate_stream(req.prompt, req.length, req.max_revision_rounds),
            media_type="text/event-stream",
        )
    result = generator.generate(req.prompt, req.length, req.max_revision_rounds)
    return JSONResponse(content={"content": result["couplet"], "raw_content": result["raw_content"]})


@router.post("/complete", response_model=GenerateResponse)
async def couplet_complete(request: Request, req: GenerateRequest):
    """Complete a couplet from partial input."""
    generator = CoupletGenerator()
    if req.stream:
        return StreamingResponse(
            generator.complete_stream(req.prompt, req.length, req.max_revision_rounds),
            media_type="text/event-stream",
        )
    result = generator.complete(req.prompt, req.length, req.max_revision_rounds)
    return JSONResponse(content={"content": result["couplet"], "raw_content": result["raw_content"]})


@router.get("/history")
async def couplet_history(x_session_id: str = Header(default=None, alias="X-Session-ID")):
    """Get couplet analysis history for a session."""
    if not x_session_id:
        return {"items": []}
    try:
        db = get_db_manager()
        records = db.get_session_history(x_session_id)
        return {"items": records}
    except Exception as e:
        logger.warning(f"Failed to load history: {e}")
        return {"items": []}


@router.get("/statistics")
async def couplet_statistics():
    """Get global statistics."""
    try:
        db = get_db_manager()
        cache = get_cache_service()
        return {
            "total_analyses": db.get_total_count(),
            "cache_size": cache.size() if hasattr(cache, "size") else 0,
        }
    except Exception as e:
        logger.warning(f"Failed to load statistics: {e}")
        return {"total_analyses": 0, "cache_size": 0}
