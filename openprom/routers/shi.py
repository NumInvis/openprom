"""Regulated verse (lüshi / jueju) generation / completion router."""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from openprom.routers.common import GenerateRequest, GenerateResponse
from openprom.services.shi_generator import ShiGenerator

router = APIRouter(prefix="/api/v1/shi", tags=["律诗"])


@router.post("/generate", response_model=GenerateResponse)
async def shi_generate(request: Request, req: GenerateRequest):
    """Generate a regulated verse from a prompt."""
    generator = ShiGenerator()
    if req.stream:
        return StreamingResponse(
            generator.generate_stream(
                req.prompt, req.form, req.tone_preference, req.max_revision_rounds
            ),
            media_type="text/event-stream",
        )
    result = generator.generate(req.prompt, req.form, req.tone_preference, req.max_revision_rounds)
    return JSONResponse(content={"content": result["poem"], "raw_content": result["raw_content"]})


@router.post("/complete", response_model=GenerateResponse)
async def shi_complete(request: Request, req: GenerateRequest):
    """Complete / continue a regulated verse."""
    generator = ShiGenerator()
    if req.stream:
        return StreamingResponse(
            generator.complete_stream(
                req.prompt, req.form, req.tone_preference, req.max_revision_rounds
            ),
            media_type="text/event-stream",
        )
    result = generator.complete(req.prompt, req.form, req.tone_preference, req.max_revision_rounds)
    return JSONResponse(content={"content": result["poem"], "raw_content": result["raw_content"]})
