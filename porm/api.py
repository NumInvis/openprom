"""PORM REST API 服务

版本：4.2.0
功能:
    - 对联评分 API
    - 诗律检测 API
    - 词牌检测 API
    - 健康检查
    - Prometheus 指标
"""

import time
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
import json as json_module

from porm.core.dual_api_scorer import DualAPITechniqueScorer, DualAPIScore
from porm.engines.meter import MeterEngine
from porm.engines.pingze import get_sequence
from porm.utils.env_config import (
    get_api_key, get_base_url, get_model,
    get_host, get_port, is_debug
)
from porm.infrastructure.database import db_manager
from porm.infrastructure.cache import cache_service, get_cache_key_couplet
from porm.infrastructure.logging import get_logger

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


class CoupletRequest(BaseModel):
    """对联评分请求"""
    upper: str = Field(..., description="上联", min_length=1, max_length=100)
    lower: str = Field(..., description="下联", min_length=1, max_length=100)
    enable_cache: bool = Field(default=True, description="是否启用缓存")
    stream: bool = Field(default=False, description="是否启用流式输出")


class StreamEvent(BaseModel):
    """流式事件"""
    event: str
    data: dict
    timestamp: float


class CoupletResponse(BaseModel):
    """对联评分响应"""
    upper: str
    lower: str
    formal_score: float
    technique_score: float
    artistic_score: float
    impression_score: float
    total_score: float
    grade: str
    pingze_score: float
    warnings: List[str]
    comments: dict
    processing_time_ms: float
    cached: Optional[bool] = None


class MeterRequest(BaseModel):
    """格律检测请求"""
    text: str = Field(..., description="诗词文本", min_length=1, max_length=500)
    meter_type: str = Field(default="shi", description="类型：shi 或 ci")


class MeterResponse(BaseModel):
    """格律检测响应"""
    text: str
    meter_type: str
    matched_meters: List[dict]
    pingze_sequence: List[int]
    violations: List[str]
    is_compliant: bool


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: str
    model: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    logger.info("PORM API 服务启动中...")
    app.state.api_key = get_api_key()
    app.state.base_url = get_base_url()
    app.state.model = get_model()
    
    # Initialize database tables
    try:
        db_manager.create_tables()
        logger.info("数据库表已初始化")
    except Exception as e:
        logger.warning(f"数据库初始化跳过：{e}")
    
    # Initialize scorer lazily on first request to avoid blocking startup
    app.state.scorer = None
    logger.info(f"使用模型：{app.state.model}")
    yield
    logger.info("PORM API 服务关闭中...")
    if app.state.scorer:
        app.state.scorer.shutdown()


def _ensure_scorer(app) -> DualAPITechniqueScorer:
    """确保评分器已初始化（线程安全单例）"""
    scorer = getattr(app.state, 'scorer', None)
    if scorer is None:
        scorer = DualAPITechniqueScorer(
            api_key=getattr(app.state, 'api_key', get_api_key()),
            base_url=getattr(app.state, 'base_url', get_base_url()),
            model=getattr(app.state, 'model', get_model())
        )
        app.state.scorer = scorer
    return scorer


app = FastAPI(
    title="PORM API",
    description="对联自动评分系统 - 基于 NLP+LLM 的企业级评分引擎",
    version="4.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（使用 pathlib）
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


def _score_to_response(
    score: DualAPIScore,
    processing_time: float
) -> CoupletResponse:
    """将评分结果转换为 API 响应"""
    return CoupletResponse(
        upper=score.upper,
        lower=score.lower,
        formal_score=round(score.formal_score, 4),
        technique_score=round(score.technique_score, 4),
        artistic_score=round(score.artistic_score, 4),
        impression_score=round(score.impression_score, 4),
        total_score=round(score.total_score, 1),
        grade=score.grade,
        pingze_score=round(score.pingze_score, 4),
        warnings=score.warnings,
        comments=score.comments,
        processing_time_ms=round(processing_time * 1000, 2),
        cached=False
    )


@app.get("/", response_class=FileResponse)
async def root():
    """返回前端首页"""
    index_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    if index_path.exists():
        return str(index_path)
    return {
        "name": "PORM API",
        "version": "4.2.0",
        "description": "对联自动评分系统",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    scorer = getattr(app.state, 'scorer', None)
    scorer_health = True
    if scorer is not None:
        scorer_health = getattr(scorer, '_healthy', True)
    
    return HealthResponse(
        status="healthy" if scorer_health else "degraded",
        version="4.2.0",
        timestamp=datetime.now().isoformat(),
        model=getattr(app.state, 'model', get_model())
    )


async def _generate_stream(upper: str, lower: str, start_time: float):
    """生成流式响应（异步生成器）"""
    try:
        yield f"data: {json_module.dumps({'event': 'start', 'timestamp': time.time()})}\n\n"
        await asyncio.sleep(0.05)
        
        yield f"data: {json_module.dumps({'event': 'formal_check', 'data': {'status': 'checking', 'message': '形式检测中...'}, 'timestamp': time.time()})}\n\n"
        await asyncio.sleep(0.05)
        
        scorer = _ensure_scorer(app)
        result = await asyncio.to_thread(scorer.analyze, upper, lower)
        
        processing_time = time.time() - start_time
        
        yield f"data: {json_module.dumps({'event': 'formal_check', 'data': {'status': 'complete', 'formal_score': result.formal_score, 'pingze_score': result.pingze_score, 'warnings': result.warnings}, 'timestamp': time.time()})}\n\n"
        await asyncio.sleep(0.05)
        
        yield f"data: {json_module.dumps({'event': 'technique_analysis', 'data': {'status': 'complete', 'technique_score': result.technique_score}, 'timestamp': time.time()})}\n\n"
        await asyncio.sleep(0.05)
        
        yield f"data: {json_module.dumps({'event': 'artistic_analysis', 'data': {'status': 'complete', 'artistic_score': result.artistic_score, 'impression_score': result.impression_score}, 'timestamp': time.time()})}\n\n"
        await asyncio.sleep(0.05)
        
        final_result = _score_to_response(result, processing_time)
        yield f"data: {json_module.dumps({'event': 'complete', 'data': jsonable_encoder(final_result), 'timestamp': time.time()})}\n\n"
        
        yield f"data: {json_module.dumps({'event': 'end', 'timestamp': time.time()})}\n\n"
        
    except Exception as e:
        logger.error(f"流式评分失败：{e}", exc_info=True)
        yield f"data: {json_module.dumps({'event': 'error', 'error': str(e), 'timestamp': time.time()})}\n\n"


@app.post("/api/v1/couplet/analyze")
async def analyze_couplet(request: CoupletRequest):
    """分析对联并评分
    
    这是核心 API 端点，提供完整的对联评分功能。
    支持流式输出 (SSE)。
    """
    start_time = time.time()
    
    if PROMETHEUS_AVAILABLE:
        REQUEST_COUNT.labels(
            endpoint="/api/v1/couplet/analyze",
            method="POST",
            status="started"
        ).inc()
    
    try:
        if len(request.upper) != len(request.lower):
            raise HTTPException(
                status_code=400,
                detail=f"上下联字数不等：上联{len(request.upper)}字，下联{len(request.lower)}字"
            )
        
        # Check cache
        if request.enable_cache:
            cache_key = get_cache_key_couplet(request.upper, request.lower)
            cached = cache_service.get("couplet", cache_key)
            if cached:
                logger.info("缓存命中")
                cached["cached"] = True
                cached["processing_time_ms"] = 0.1
                return CoupletResponse(**cached)
        
        if request.stream:
            return StreamingResponse(
                _generate_stream(request.upper, request.lower, start_time),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        scorer = _ensure_scorer(app)
        result = await asyncio.to_thread(scorer.analyze, request.upper, request.lower)
        
        processing_time = time.time() - start_time
        
        response = _score_to_response(result, processing_time)
        
        # Save to database
        try:
            db_manager.save_couplet_analysis(result)
        except Exception as db_err:
            logger.warning(f"数据库保存失败：{db_err}")
        
        # Save to cache
        if request.enable_cache:
            try:
                cache_service.set("couplet", cache_key, jsonable_encoder(response))
            except Exception as cache_err:
                logger.warning(f"缓存写入失败：{cache_err}")
        
        if PROMETHEUS_AVAILABLE:
            REQUEST_LATENCY.labels(
                endpoint="/api/v1/couplet/analyze"
            ).observe(processing_time)
            REQUEST_COUNT.labels(
                endpoint="/api/v1/couplet/analyze",
                method="POST",
                status="success"
            ).inc()
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"评分失败：{e}", exc_info=True)
        
        if PROMETHEUS_AVAILABLE:
            REQUEST_COUNT.labels(
                endpoint="/api/v1/couplet/analyze",
                method="POST",
                status="error"
            ).inc()
        
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/meter/check", response_model=MeterResponse)
async def check_meter(request: MeterRequest):
    """检查诗词格律"""
    start_time = time.time()
    
    try:
        pingze_seq = get_sequence(request.text)
        engine = MeterEngine()
        
        lines = [request.text]
        
        if request.meter_type == "shi":
            matched = engine.find_best_shi(lines, top_k=1)
            meters = [m.to_dict() for m in matched] if matched else []
        elif request.meter_type == "ci":
            matched = engine.find_best_ci(lines, top_k=1)
            meters = [m.to_dict() for m in matched] if matched else []
        else:
            raise HTTPException(status_code=400, detail=f"不支持的 meter_type: {request.meter_type}")
        
        violations = []
        for meter in meters:
            if meter.get("match_rate", 1.0) < 0.8:
                violations.append(f"格律匹配度不足：{meter.get('match_rate', 0):.2%}")
        
        time.time() - start_time
        
        return MeterResponse(
            text=request.text,
            meter_type=request.meter_type,
            matched_meters=meters,
            pingze_sequence=pingze_seq,
            violations=violations,
            is_compliant=len(violations) == 0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"格律检测失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/meters/list")
async def list_meters(meter_type: Optional[str] = "all"):
    """列出所有可用的格律模板"""
    try:
        from porm.data.loader import MeterPattern
        patterns = MeterPattern.get()
        
        if meter_type == "all":
            return {
                "shi_meters": patterns.list_shi_patterns()[:20],
                "ci_meters": patterns.list_ci_patterns()[:50]
            }
        elif meter_type == "shi":
            return {"meters": patterns.list_shi_patterns()}
        elif meter_type == "ci":
            return {"meters": patterns.list_ci_patterns()}
        else:
            raise HTTPException(status_code=400, detail="无效的 meter_type")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出格律失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/couplet/history")
async def get_couplet_history(limit: int = 20, offset: int = 0):
    """获取评鉴历史记录"""
    try:
        records = db_manager.get_couplet_history(limit=limit, offset=offset)
        return {
            "total": len(records),
            "offset": offset,
            "limit": limit,
            "records": [r.to_dict() for r in records]
        }
    except Exception as e:
        logger.error(f"获取历史记录失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/couplet/statistics")
async def get_couplet_statistics():
    """获取评鉴统计信息"""
    try:
        stats = db_manager.get_statistics()
        cache_stats = cache_service.get_stats()
        return {
            "database": stats,
            "cache": cache_stats
        }
    except Exception as e:
        logger.error(f"获取统计信息失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if PROMETHEUS_AVAILABLE:
    @app.get("/metrics")
    async def metrics():
        """Prometheus 指标"""
        return StreamingResponse(
            generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )


if __name__ == "__main__":
    import uvicorn
    
    host = get_host()
    port = get_port()
    debug = is_debug()
    
    logger.info(f"启动服务：http://{host}:{port}")
    logger.info(f"API 文档：http://{host}:{port}/docs")
    
    uvicorn.run(
        "porm.api:app",
        host=host,
        port=port,
        reload=debug,
        log_level="debug" if debug else "info"
    )
