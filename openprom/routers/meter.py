"""Meter detection router."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from openprom.routers.common import MeterRequest, MeterResponse
from openprom.services.meter_tool import check_meter

router = APIRouter(prefix="/api/v1/meter", tags=["格律检测"])


@router.post("/check", response_model=MeterResponse)
async def meter_check(request: Request, req: MeterRequest):
    """Check meter for shi, ci or couplet.

    This endpoint is also exposed as a Tool for LLM agents.
    """
    result = check_meter(
        text=req.text,
        meter_type=req.meter_type,
        pattern_name=req.pattern_name,
        strict=req.strict,
    )
    return JSONResponse(content=result)


@router.get("/list")
async def meter_list(meter_type: str = "shi"):
    """List available meter patterns."""
    from openprom.data.loader import MeterPattern
    patterns = MeterPattern.get()
    if meter_type == "shi":
        return {"meter_type": "shi", "patterns": patterns.list_shi_patterns()}
    if meter_type == "ci":
        return {"meter_type": "ci", "patterns": patterns.list_ci_patterns()}
    return {"meter_type": meter_type, "patterns": []}
