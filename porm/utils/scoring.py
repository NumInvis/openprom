"""评分计算工具

提供分数计算、归一化等通用功能。
"""

import numpy as np
from typing import Union


def normalize_score(score: Union[int, float], max_score: float = 100.0) -> float:
    """线性归一化"""
    return float(score) / max_score


def normalize_cosine_similarity(raw_score: float) -> float:
    """将余弦相似度 [-1, 1] 归一化到 [0, 1]"""
    return float(np.clip((raw_score + 1) / 2, 0.0, 1.0))


def normalize_zscore_sigmoid(
    raw_score: float,
    mean: float = 0.0,
    std: float = 1.0,
    min_val: float = 0.0,
    max_val: float = 1.0
) -> float:
    """Z-score + Sigmoid 归一化
    
    参数:
        raw_score: 原始分数
        mean: 期望均值
        std: 期望标准差
        min_val: 输出最小值
        max_val: 输出最大值
    
    返回:
        归一化后的分数
    """
    z_score = (raw_score - mean) / std if std > 0 else 0
    sigmoid = 1 / (1 + np.exp(-z_score))
    return float(min_val + (max_val - min_val) * sigmoid)


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
