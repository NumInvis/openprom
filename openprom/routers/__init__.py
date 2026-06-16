"""OpenPROM API routers."""

from openprom.routers.meter import router as meter_router
from openprom.routers.couplet import router as couplet_router
from openprom.routers.shi import router as shi_router
from openprom.routers.health import router as health_router

__all__ = ["meter_router", "couplet_router", "shi_router", "health_router"]
