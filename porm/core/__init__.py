"""核心领域层 (Core Domain Layer)

包含系统的核心业务逻辑。
"""

from porm.core.analyzer_interface import (
    CoupletAnalyzerInterface,
    AnalysisResult,
    create_analyzer,
)
from porm.core.analyzer import (
    CoupletAnalyzer,
    CoupletScore,
    analyze,
)
from porm.core.base_analyzer import (
    analyze_formal,
    generate_overall_comment,
    calculate_total_score,
    determine_grade,
)
from porm.core.saddle_engineering import (
    SaddleEngineering,
    InputController,
    ProcessController,
    OutputController,
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

__all__ = [
    # Interface (统一接口)
    "CoupletAnalyzerInterface",
    "AnalysisResult",
    "create_analyzer",
    # Analyzer (兼容层 + 实现)
    "CoupletAnalyzer",
    "CoupletScore",
    "analyze",
    # Base Analyzer (shared utilities)
    "analyze_formal",
    "generate_overall_comment",
    "calculate_total_score",
    "determine_grade",
    # Saddle Engineering
    "SaddleEngineering",
    "InputController",
    "ProcessController",
    "OutputController",
    "ControlContext",
    "ConstraintViolation",
    "ConstraintType",
    # Fusion Engine
    "FusionEngine",
    "FusionResult",
    "NLPFeatures",
    "LLMOutput",
    "FusionStrategy",
]
