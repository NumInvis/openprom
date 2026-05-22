"""诗律词谱匹配引擎

提供诗律和词谱的格律匹配功能。
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import IntEnum

import threading
from porm.data.loader import MeterPattern
from porm.engines.pingze import get_sequence


class TonePattern(IntEnum):
    """声调模式编码"""
    FLEXIBLE = 0      # 0: 可平可仄
    PING = 1          # 1: 平声
    ZE = -1           # 2: 仄声 (映射为-1)
    PING_REQUIRED = 3 # 3: 必须是平
    ZE_REQUIRED = 4   # 4: 必须是仄


@dataclass
class MeterMatch:
    """格律匹配结果"""
    pattern_name: str
    match_rate: float
    errors: List[Dict]
    is_valid: bool

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "pattern_name": self.pattern_name,
            "match_rate": self.match_rate,
            "errors": self.errors,
            "is_valid": self.is_valid,
        }


class MeterEngine:
    """诗律词谱匹配引擎"""

    # 默认匹配阈值
    DEFAULT_VALID_THRESHOLD = 0.8

    def __init__(self, threshold: float = DEFAULT_VALID_THRESHOLD):
        self._patterns = MeterPattern.get()
        self._threshold = threshold

    def _match_line(self, text: str, pattern: List[int]) -> Tuple[float, List[Dict]]:
        """单行文本与格律模式匹配

        Args:
            text: 待匹配文本
            pattern: 格律模式列表

        Returns:
            (匹配率, 错误列表)
        """
        tones = get_sequence(text)
        errors = []
        match_count = 0
        total = 0

        for i, (t, p) in enumerate(zip(tones, pattern)):
            if p == TonePattern.FLEXIBLE:
                continue

            total += 1

            # 判断平仄是否匹配
            expected_tone = None
            is_match = False

            if p == TonePattern.PING_REQUIRED:
                expected_tone = "平"
                is_match = (t == 1)  # Must be ping, zhong (0) is not acceptable
            elif p == TonePattern.ZE_REQUIRED:
                expected_tone = "仄"
                is_match = (t == -1)  # Must be ze, zhong (0) is not acceptable
            elif p == TonePattern.PING:
                expected_tone = "平"
                is_match = (t == 1 or t == 0)  # Ping or zhong is acceptable
            elif p == TonePattern.ZE:
                expected_tone = "仄"
                is_match = (t == -1 or t == 0)  # Ze or zhong is acceptable

            if is_match:
                match_count += 1
            elif expected_tone:
                errors.append({
                    "pos": i,
                    "char": text[i],
                    "expected": expected_tone,
                    "actual": "平" if t == 1 else "仄" if t == -1 else "中"
                })

        if total == 0:
            return 1.0, []

        return match_count / total, errors

    def _match_pattern(
        self,
        lines: List[str],
        pattern: Optional[List[List[int]]],
        pattern_name: str
    ) -> MeterMatch:
        """通用格律匹配

        Args:
            lines: 诗句列表
            pattern: 格律模式
            pattern_name: 模式名称

        Returns:
            MeterMatch对象
        """
        if pattern is None:
            return MeterMatch(
                pattern_name=pattern_name,
                match_rate=0.0,
                errors=[{"error": "pattern not found"}],
                is_valid=False
            )

        if len(lines) != len(pattern):
            return MeterMatch(
                pattern_name=pattern_name,
                match_rate=0.0,
                errors=[{
                    "error": f"line count mismatch: {len(lines)} vs {len(pattern)}"
                }],
                is_valid=False
            )

        all_errors = []
        total_match = 0.0

        for i, (line, pat) in enumerate(zip(lines, pattern)):
            rate, errors = self._match_line(line, pat)
            total_match += rate
            for e in errors:
                e["line"] = i
            all_errors.extend(errors)

        avg_match = total_match / len(lines)
        is_valid = avg_match >= self._threshold

        return MeterMatch(
            pattern_name=pattern_name,
            match_rate=avg_match,
            errors=all_errors,
            is_valid=is_valid
        )

    def match_shi(self, lines: List[str], pattern_name: str) -> MeterMatch:
        """匹配诗体格律"""
        pattern = self._patterns.get_shi_pattern(pattern_name)
        return self._match_pattern(lines, pattern, pattern_name)

    def match_ci(self, lines: List[str], pattern_name: str) -> MeterMatch:
        """匹配词牌格律"""
        pattern = self._patterns.get_ci_pattern(pattern_name)
        return self._match_pattern(lines, pattern, pattern_name)

    def find_best_patterns(
        self,
        lines: List[str],
        pattern_type: str,
        top_k: int = 5
    ) -> List[MeterMatch]:
        """查找最佳匹配的模式

        Args:
            lines: 诗句列表
            pattern_type: 'shi' 或 'ci'
            top_k: 返回前k个结果

        Returns:
            按匹配率排序的MeterMatch列表
        """
        if pattern_type == "shi":
            patterns = self._patterns.list_shi_patterns()
            match_func = self.match_shi
        elif pattern_type == "ci":
            patterns = self._patterns.list_ci_patterns()
            match_func = self.match_ci
        else:
            raise ValueError(f"Unknown pattern_type: {pattern_type}")

        results = []
        for name in patterns:
            match = match_func(lines, name)
            results.append(match)

        results.sort(key=lambda x: -x.match_rate)
        return results[:top_k]

    def find_best_shi(self, lines: List[str], top_k: int = 5) -> List[MeterMatch]:
        """查找最佳匹配的诗体"""
        return self.find_best_patterns(lines, "shi", top_k)

    def find_best_ci(self, lines: List[str], top_k: int = 5) -> List[MeterMatch]:
        """查找最佳匹配的词牌"""
        return self.find_best_patterns(lines, "ci", top_k)


# 全局引擎实例（线程安全）
_engine: Optional[MeterEngine] = None
_engine_lock: threading.Lock = threading.Lock()


def get_engine(threshold: float = MeterEngine.DEFAULT_VALID_THRESHOLD) -> MeterEngine:
    """获取全局引擎实例（线程安全）"""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = MeterEngine(threshold=threshold)
    return _engine


def match_shi(lines: List[str], pattern_name: str) -> MeterMatch:
    """匹配诗体格律的便捷函数"""
    return get_engine().match_shi(lines, pattern_name)


def match_ci(lines: List[str], pattern_name: str) -> MeterMatch:
    """匹配词牌格律的便捷函数"""
    return get_engine().match_ci(lines, pattern_name)


def find_best_shi(lines: List[str], top_k: int = 5) -> List[MeterMatch]:
    """查找最佳诗体的便捷函数"""
    return get_engine().find_best_shi(lines, top_k)


def find_best_ci(lines: List[str], top_k: int = 5) -> List[MeterMatch]:
    """查找最佳词牌的便捷函数"""
    return get_engine().find_best_ci(lines, top_k)
