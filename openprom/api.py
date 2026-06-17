"""OpenPROM REST API 服务

版本：4.3.0
功能:
    - 对联评分 / 生成 / 补全
    - 律诗生成 / 补全
    - 格律检测（同时作为 LLM Tool）
    - 健康检查
    - Prometheus 指标
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from openprom import __version__
from openprom.routers import (
    meter_router,
    couplet_router,
    shi_router,
    health_router,
    knowledge_router,
    tasks_router,
)
from openprom.infrastructure.database import get_db_manager
from openprom.infrastructure.logging import get_logger
from openprom.utils.env_config import (
    get_api_key, get_base_url, get_model,
    get_host, get_port, is_debug
)

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = get_logger(__name__)

if PROMETHEUS_AVAILABLE:
    REQUEST_COUNT = Counter(
        'porm_requests_total',
        'Total API requests',
        ['endpoint', 'method', 'status']
    )
    REQUEST_LATENCY = Histogram(
        'porm_request_latency_seconds',
        'API request latency',
        ['endpoint']
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    logger.info("OpenPROM API 服务启动中...")
    app.state.api_key = get_api_key()
    app.state.base_url = get_base_url()
    app.state.model = get_model()

    try:
        get_db_manager().create_tables()
        logger.info("数据库表已初始化")
    except Exception as e:
        logger.warning(f"数据库初始化跳过：{e}")

    # Scorer and LLM client are initialized lazily on first request.
    app.state.scorer = None
    logger.info(f"使用模型：{app.state.model}")
    yield
    logger.info("OpenPROM API 服务关闭中...")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="OpenPROM API",
        description="纯 AI 应用层诗词助手：对联评分、生成、补全；律诗生成、补全；格律检测。",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("OPENPROM_CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory="frontend"), name="static")

    app.include_router(health_router)
    app.include_router(meter_router)
    app.include_router(couplet_router)
    app.include_router(shi_router)
    app.include_router(knowledge_router)
    app.include_router(tasks_router)

    if PROMETHEUS_AVAILABLE:
        @app.get("/metrics")
        async def metrics():
            from fastapi import Response
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/")
    async def root():
        return FileResponse("frontend/index.html")

    return app


app = create_app()


def main():
    """CLI entrypoint."""
    import uvicorn
    uvicorn.run(
        "openprom.api:app",
        host=get_host(),
        port=get_port(),
        reload=is_debug(),
    )


if __name__ == "__main__":
    main()
