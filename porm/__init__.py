"""PORM - 对联自动评分系统 v4.2

基于 NLP + LLM 的企业级中文对联评分系统。
"""

__version__ = "4.2.0"
__author__ = "porm contributors"

# Core
from porm.core.analyzer import (
    CoupletAnalyzer,
    CoupletScore,
    analyze,
)
from porm.core.saddle_engineering import (
    SaddleEngineering,
    ControlContext,
    ConstraintViolation,
    ConstraintType,
)
from porm.core.fusion_engine import (
    FusionEngine,
    FusionResult,
    NLPFeatures,
    LLMOutput,
    FusionStrategy,
)

# Engines
from porm.engines.meter import (
    MeterEngine,
    MeterMatch,
    TonePattern,
    match_shi,
    match_ci,
    find_best_shi,
    find_best_ci,
)
from porm.engines.pingze import (
    PingZeEngine,
    PingZeResult,
    PingZeValue,
    ConfidenceLevel,
    analyze as pingze_analyze,
    get_sequence,
    get_stats,
)

# Infrastructure
from porm.infrastructure.config import (
    PromptConfigService,
    PromptTemplate,
    PromptConfig,
    PromptType,
    get_prompt_service,
)

# Data
from porm.data.loader import RhymeBook, MeterPattern

# Utils
from porm.utils import (
    parse_llm_json_response,
    normalize_score,
    clamp_score,
    load_config,
    classify_similarity_level,
)

from porm.core.analyzer_interface import AnalysisResult

__all__ = [
    "__version__",
    # Core - Interface
    "CoupletAnalyzerInterface",
    "AnalysisResult",
    "create_analyzer",
    # Core - Implementation
    "CoupletAnalyzer",
    "CoupletScore",
    "analyze",
    "SaddleEngineering",
    "ControlContext",
    "ConstraintViolation",
    "ConstraintType",
    "FusionEngine",
    "FusionResult",
    "NLPFeatures",
    "LLMOutput",
    "FusionStrategy",
    # Engines
    "MeterEngine",
    "MeterMatch",
    "TonePattern",
    "match_shi",
    "match_ci",
    "find_best_shi",
    "find_best_ci",
    "PingZeEngine",
    "PingZeResult",
    "PingZeValue",
    "ConfidenceLevel",
    "pingze_analyze",
    "get_sequence",
    "get_stats",
    # Infrastructure
    "PromptConfigService",
    "PromptTemplate",
    "PromptConfig",
    "PromptType",
    "get_prompt_service",
    # Data
    "RhymeBook",
    "MeterPattern",
    
    # Utils
    "parse_llm_json_response",
    "normalize_score",
    "clamp_score",
    "load_config",
    "classify_similarity_level",
]
