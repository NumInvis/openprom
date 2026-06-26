"""评分计算工具

提供分数计算、归一化等通用功能。
"""

from typing import Union


def normalize_score(score: Union[int, float], max_score: float = 100.0) -> float:
    """线性归一化"""
    return float(score) / max_score


def clamp_score(value: Union[int, float], min_val: float = 0.0, max_val: float = 100.0) -> float:
    """限制分数范围"""
    return max(min_val, min(max_val, float(value)))


def calculate_weighted_score(scores: list[float], weights: list[float]) -> float:
    """加权平均分数"""
    if len(scores) != len(weights):
        raise ValueError(f"分数数量 ({len(scores)}) 与权重数量 ({len(weights)}) 不匹配")

    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0

    normalized_weights = [w / total_weight for w in weights]
    return sum(s * w for s, w in zip(scores, normalized_weights))
