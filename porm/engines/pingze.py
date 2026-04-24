"""平仄检测引擎

提供汉字平仄声调的检测功能。
支持多种数据源：韵书、拼音库
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import IntEnum
import threading

from porm.data.loader import RhymeBook


class PingZeValue(IntEnum):
    """平仄值枚举"""
    ZE = -1   # 仄声
    ZHONG = 0 # 中声（不确定）
    PING = 1  # 平声


class ConfidenceLevel(IntEnum):
    """置信度等级"""
    UNKNOWN = 0     # 未知
    LOW = 1         # 低（拼音推断）
    MEDIUM = 2      # 中（多音字）
    HIGH = 3        # 高（韵书确认）


@dataclass(frozen=True)
class PingZeResult:
    """平仄分析结果

    Attributes:
        char: 分析的汉字
        pingze: 平仄值 (-1=仄, 0=中, 1=平)
        method: 分析方法
        confidence: 置信度 (0-1)
    """
    char: str
    pingze: int
    method: str
    confidence: float

    def __post_init__(self):
        # 验证置信度范围
        if not 0.0 <= self.confidence <= 1.0:
            object.__setattr__(self, 'confidence', max(0.0, min(1.0, self.confidence)))


class PingZeEngine:
    """平仄检测引擎

    支持多级数据源：
    1. 韵书查询（最高优先级）
    2. pypinyin拼音库（备用）
    3. 默认未知（兜底）
    """

    # 置信度配置
    CONFIDENCE_RHYMEBOOK = 0.95  # 韵书置信度
    CONFIDENCE_PYPINYIN = 0.60   # 拼音库置信度
    CONFIDENCE_UNKNOWN = 0.0     # 未知置信度

    def __init__(self, default_book: str = "平水韵"):
        """初始化引擎

        Args:
            default_book: 默认使用的韵书名称
        """
        self._cache: Dict[str, PingZeResult] = {}
        self._rhyme = RhymeBook.get()
        self._default_book = default_book

    def analyze(self, char: str) -> PingZeResult:
        """分析单个汉字的平仄

        Args:
            char: 待分析的汉字

        Returns:
            PingZeResult对象
        """
        # 检查缓存
        if char in self._cache:
            return self._cache[char]

        # 1. 尝试韵书查询
        result = self._analyze_by_rhymebook(char)
        if result is not None:
            self._cache[char] = result
            return result

        # 2. 尝试拼音库
        result = self._analyze_by_pypinyin(char)
        if result is not None:
            self._cache[char] = result
            return result

        # 3. 返回未知
        result = PingZeResult(
            char=char,
            pingze=PingZeValue.ZHONG,
            method="unknown",
            confidence=self.CONFIDENCE_UNKNOWN
        )
        self._cache[char] = result
        return result

    def _analyze_by_rhymebook(self, char: str) -> Optional[PingZeResult]:
        """通过韵书分析平仄"""
        tone = self._rhyme.get_tone(char, self._default_book)
        if tone is not None:
            return PingZeResult(
                char=char,
                pingze=tone,
                method="rhymebook",
                confidence=self.CONFIDENCE_RHYMEBOOK
            )
        return None

    def _analyze_by_pypinyin(self, char: str) -> Optional[PingZeResult]:
        """通过pypinyin分析平仄"""
        try:
            from pypinyin import lazy_pinyin, Style

            py = lazy_pinyin(char, style=Style.FINALS_TONE3, strict=True)
            if py and py[0] and py[0][-1].isdigit():
                tone_num = int(py[0][-1])
                # 1、2声为平，3、4声为仄
                pingze = PingZeValue.PING if tone_num in (1, 2) else PingZeValue.ZE
                return PingZeResult(
                    char=char,
                    pingze=pingze,
                    method="pypinyin",
                    confidence=self.CONFIDENCE_PYPINYIN
                )
        except ImportError:
            pass
        except Exception:
            # 忽略pypinyin分析错误
            pass
        return None

    def analyze_text(self, text: str) -> List[PingZeResult]:
        """分析文本中每个字符的平仄

        Args:
            text: 待分析的文本

        Returns:
            PingZeResult列表
        """
        return [self.analyze(c) for c in text]

    def get_sequence(self, text: str) -> List[int]:
        """获取文本的平仄序列

        Args:
            text: 待分析的文本

        Returns:
            平仄值列表 (-1, 0, 1)
        """
        return [r.pingze for r in self.analyze_text(text)]

    def get_stats(self, text: str) -> Dict[str, int]:
        """获取文本平仄统计信息

        Args:
            text: 待分析的文本

        Returns:
            统计字典
        """
        sequence = self.get_sequence(text)
        return {
            "total": len(sequence),
            "ping": sum(1 for x in sequence if x == 1),
            "ze": sum(1 for x in sequence if x == -1),
            "zhong": sum(1 for x in sequence if x == 0),
        }

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# 全局引擎实例（线程安全）
_engine: Optional[PingZeEngine] = None
_engine_lock: threading.Lock = threading.Lock()


def get_engine() -> PingZeEngine:
    """获取全局引擎实例（线程安全）"""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = PingZeEngine()
    return _engine


def analyze(char: str) -> PingZeResult:
    """分析单个汉字的便捷函数"""
    return get_engine().analyze(char)


def analyze_text(text: str) -> List[PingZeResult]:
    """分析文本的便捷函数"""
    return get_engine().analyze_text(text)


def get_sequence(text: str) -> List[int]:
    """获取平仄序列的便捷函数"""
    return get_engine().get_sequence(text)


def get_stats(text: str) -> Dict[str, int]:
    """获取统计信息的便捷函数"""
    return get_engine().get_stats(text)


def clear_cache():
    """清除缓存的便捷函数"""
    get_engine().clear_cache()
