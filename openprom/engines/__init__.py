"""引擎模块

包含各类分析引擎：
- 平仄检测引擎 (pingze)
- 诗律词谱匹配引擎 (meter)
"""

from openprom.engines.pingze import PingZeEngine, PingZeResult, analyze, get_sequence
from openprom.engines.meter import MeterEngine, MeterMatch, match_shi, match_ci, find_best_shi, find_best_ci

__all__ = [
    "PingZeEngine",
    "PingZeResult",
    "analyze",
    "get_sequence",
    "MeterEngine",
    "MeterMatch",
    "match_shi",
    "match_ci",
    "find_best_shi",
    "find_best_ci",
]
