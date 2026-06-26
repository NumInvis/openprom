"""Shared models, error codes and dependencies for OpenPROM routers."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request


class PormErrorCode(str, Enum):
    """Standard error codes."""

    LENGTH_MISMATCH = "COUPLET_001"
    INVALID_CHARSET = "COUPLET_002"
    LLM_TIMEOUT = "LLM_001"
    LLM_PARSE_ERROR = "LLM_002"
    SADDLE_REJECTED = "QC_001"
    INTERNAL_ERROR = "SYS_001"
    METER_NOT_COMPLIANT = "METER_001"


class PormHTTPException(HTTPException):
    """Standard HTTP exception with error code."""

    def __init__(self, status_code: int, error_code: PormErrorCode, detail: str):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code


class DimensionBreakdown(BaseModel):
    """Dimension score breakdown."""

    score: float
    weight: float
    raw_score: Optional[float] = None
    comment: Optional[str] = None


class WordAnalysis(BaseModel):
    """Word-by-word analysis."""

    position: int
    upper_char: str
    lower_char: str
    upper_tone: Optional[int] = None
    lower_tone: Optional[int] = None
    pos_match: Optional[bool] = None
    tone_match: Optional[bool] = None
    comment: Optional[str] = None


class AnalysisDetail(BaseModel):
    """Detailed analysis."""

    word_analysis: Optional[List[WordAnalysis]] = None
    pingze_upper: Optional[List[int]] = None
    pingze_lower: Optional[List[int]] = None
    meter_pattern: Optional[str] = None
    violations: Optional[List[str]] = None


class CoupletRequest(BaseModel):
    """Couplet scoring request."""

    upper: str = Field(..., description="上联", min_length=1, max_length=100)
    lower: str = Field(..., description="下联", min_length=1, max_length=100)
    enable_cache: bool = Field(default=True, description="是否启用缓存")
    stream: bool = Field(default=False, description="是否启用流式输出")


class CoupletResponse(BaseModel):
    """Couplet scoring response."""

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
    id: Optional[int] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    error_code: Optional[str] = None
    breakdown: Optional[Dict[str, DimensionBreakdown]] = None
    detail: Optional[AnalysisDetail] = None


class MeterRequest(BaseModel):
    """Meter detection request."""

    text: str = Field(
        ...,
        description="诗词文本；律诗按行用\\n分隔，对联用\\n分隔上下联",
        min_length=1,
        max_length=500,
    )
    meter_type: str = Field(default="shi", description="类型：shi、ci、couplet")
    pattern_name: Optional[str] = Field(default=None, description="指定诗体/词牌名称")
    strict: bool = Field(default=False, description="严格模式")


class MeterResponse(BaseModel):
    """Meter detection response."""

    text: str
    meter_type: str
    matched_meters: List[dict]
    pingze_sequence: List[Any]
    violations: List[str]
    is_compliant: bool
    rhyme_suggestions: List[str] = Field(default_factory=list)
    tone_details: List[dict] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    """Generation/Completion request."""

    prompt: str = Field(..., description="主题、上联或已给出的诗句", min_length=1, max_length=500)
    length: Optional[int] = Field(default=None, description="对联每联字数（5/7）")
    form: Optional[str] = Field(default=None, description="诗体（五绝/七绝/五律/七律）")
    tone_preference: Optional[str] = Field(default=None, description="平起/仄起（可选）")
    stream: bool = Field(default=True, description="是否流式输出过程")
    max_revision_rounds: Optional[int] = Field(default=None, description="最大自修正轮数")


class GenerateResponse(BaseModel):
    """Generation/Completion response."""

    content: str
    raw_content: Optional[str] = None


def get_scorer(request: Request):
    """Dependency: obtain or create the couplet scorer from app state."""
    from openprom.services.couplet_scorer import CoupletScorer

    if not hasattr(request.app.state, "scorer") or request.app.state.scorer is None:
        request.app.state.scorer = CoupletScorer()
    return request.app.state.scorer


def get_llm_client_instance(request: Request):
    """Dependency: obtain the global LLM client."""
    from openprom.services.llm_client import get_llm_client

    return get_llm_client()


# ---------------------------------------------------------------------------
# Knowledge layer / Tasks layer models (M3)
# ---------------------------------------------------------------------------


class KnowledgeSearchRequest(BaseModel):
    """Knowledge layer retrieval request."""

    query: str = Field(..., description="检索查询", min_length=1, max_length=500)
    top_k: int = Field(default=5, description="返回结果数", ge=1, le=50)
    task_type: Optional[str] = Field(
        default=None,
        description="任务类型：generate_couplet/generate_shi/analyze_couplet/check_meter/general",
    )
    target_form: Optional[str] = Field(
        default=None,
        description="目标体裁，用于规则信号融合（如 wu jue/qi lv）",
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="ChromaDB metadata 过滤条件",
    )


class KnowledgeSearchHit(BaseModel):
    """Single retrieval hit."""

    id: str
    content: str
    annotated: str
    chunk_type: str
    final_score: float
    semantic_score: float
    rerank_score: Optional[float] = None
    rule_signals: Dict[str, float] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    """Knowledge layer retrieval response."""

    query: str
    total_candidates: int
    pipeline_stages: List[str]
    results: List[KnowledgeSearchHit]
    latency_ms: float


class KnowledgeStatsResponse(BaseModel):
    """Knowledge layer statistics."""

    enabled: bool
    knowledge_layer_v2: bool
    vector_store_size: int
    retrieval_cache: Dict[str, Any]
    rerank_cache: Dict[str, Any]
    embedding_provider: str
    rerank_provider: str
    skills: List[str]


class TaskListResponse(BaseModel):
    """Registered task list."""

    tasks: List[Dict[str, Any]]


class TraceListItem(BaseModel):
    """Trace summary for the list endpoint."""

    task_id: str
    task_name: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    total_duration_ms: float
    llm_calls: int
    tool_calls: int
    rag_calls: int
    success: bool
    error: Optional[str] = None


class TraceDetailResponse(TraceListItem):
    """Full trace including step list."""

    steps: List[Dict[str, Any]] = Field(default_factory=list)


class TaskRunRequest(BaseModel):
    """Run an arbitrary registered task via AgentRunner."""

    task_name: str = Field(..., description="任务名（必须已在 TaskRegistry 中注册）")
    user_prompt: str = Field(..., description="用户输入", min_length=1, max_length=2000)
    system_prompt: Optional[str] = Field(default=None, description="覆盖任务默认 system prompt")
    max_rounds: Optional[int] = Field(
        default=None, description="覆盖任务的最大 LLM 轮数", ge=1, le=10
    )
    extra_context: Optional[str] = Field(
        default=None, description="附加上下文（例如已检索到的范例）"
    )


class TaskRunResponse(BaseModel):
    """Result of running a task via AgentRunner."""

    content: str
    trace: TraceDetailResponse
