"""OpenPROM - 诗词 AI 应用层 v4.3

纯 AI 应用层中文诗词助手：对联评分、生成、补全；律诗生成、补全；格律检测。
"""

__version__ = "4.3.0"
__author__ = "OpenPROM contributors"

from openprom.services.couplet_scorer import CoupletScorer, CoupletScore, score_couplet

from openprom.core.saddle_engineering import (
    SaddleEngineering,
    ControlContext,
    ConstraintViolation,
    ConstraintType,
)

from openprom.engines.meter import (
    MeterEngine,
    MeterMatch,
    TonePattern,
    match_shi,
    match_ci,
    find_best_shi,
    find_best_ci,
)

from openprom.engines.pingze import (
    PingZeEngine,
    PingZeResult,
    PingZeValue,
    analyze as pingze_analyze,
    get_sequence,
    get_stats,
)

from openprom.infrastructure.config import (
    PromptConfigService,
    PromptTemplate,
    PromptConfig,
    PromptType,
    get_prompt_service,
)

from openprom.data.loader import RhymeBook, MeterPattern

from openprom.utils import (
    parse_llm_json_response,
    normalize_score,
    clamp_score,
)

__all__ = [
    "__version__",
    "CoupletScorer",
    "CoupletScore",
    "score_couplet",
    "SaddleEngineering",
    "ControlContext",
    "ConstraintViolation",
    "ConstraintType",
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
    "pingze_analyze",
    "get_sequence",
    "get_stats",
    "PromptConfigService",
    "PromptTemplate",
    "PromptConfig",
    "PromptType",
    "get_prompt_service",
    "RhymeBook",
    "MeterPattern",
    "parse_llm_json_response",
    "normalize_score",
    "clamp_score",
]
