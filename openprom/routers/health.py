"""Health check router."""

from datetime import datetime
from fastapi import APIRouter, Request

from openprom import __version__

router = APIRouter(tags=["健康"])


@router.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    model = getattr(request.app.state, "model", "unknown")
    return {
        "status": "ok",
        "version": __version__,
        "timestamp": datetime.now().isoformat(),
        "model": model,
    }
