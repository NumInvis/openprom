"""分析器基础模块 (Analyzer Base Module)

提取所有分析器的公共逻辑，消除代码重复。
包含：形式分析、评语生成、评分计算、评级判定等共享功能。
"""

from typing import Tuple, List
from porm.engines.pingze import get_sequence


def analyze_formal(upper: str, lower: str) -> Tuple[float, float, List[str]]:
    """形式分析：平仄、字数、格律（统一实现）
    
    Args:
        upper: 上联
        lower: 下联
        
    Returns:
        (formal_score, pingze_score, warnings)
    """
    if len(upper) != len(lower):
        return 0.0, 0.0, ["字数不等"]
    
    u_tones = get_sequence(upper)
    l_tones = get_sequence(lower)
    warnings = []
    
    # 二四六分明
    key_pos = list(range(1, len(upper), 2))
    correct = sum(1 for i in key_pos if u_tones[i] * l_tones[i] == -1)
    er_si_score = correct / len(key_pos) if key_pos else 1.0
    
    # 仄起平落
    ze_ping_score = 1.0
    if u_tones[-1] != -1:
        warnings.append("上联尾字非仄声")
        ze_ping_score -= 0.5
    if l_tones[-1] != 1:
        warnings.append("下联尾字非平声")
        ze_ping_score -= 0.5
    
    # 三仄尾/三平尾
    for name, tones in [("上联", u_tones), ("下联", l_tones)]:
        if len(tones) >= 3:
            last3 = [t for t in tones[-3:] if t != 0]
            if len(last3) == 3:
                if all(t < 0 for t in last3):
                    warnings.append(f"{name}三仄尾")
                if all(t > 0 for t in last3):
                    warnings.append(f"{name}三平尾")
    
    pingze_score = 0.7 * er_si_score + 0.3 * max(0, ze_ping_score)
    return pingze_score, pingze_score, warnings


def generate_overall_comment(formal_score: float, technique_score: float, artistic_score: float) -> str:
    """生成总评（统一实现）
    
    Args:
        formal_score: 形式合规得分 (0-1)
        technique_score: 对仗技术得分 (0-1)
        artistic_score: 艺术表现得分 (0-1)
        
    Returns:
        总评文字
    """
    parts = []
    
    if formal_score >= 0.8:
        parts.append("形式合规，平仄协调")
    elif formal_score >= 0.6:
        parts.append("形式基本合规，略有瑕疵")
    else:
        parts.append("形式有待改进")
    
    if technique_score >= 0.8:
        parts.append("对仗技法娴熟（基于BERT+LLM双重验证）")
    elif technique_score >= 0.6:
        parts.append("对仗尚可（经多维度算法验证）")
    
    if artistic_score >= 0.8:
        parts.append("意境深远，修辞精妙")
    elif artistic_score >= 0.6:
        parts.append("有一定艺术价值")
    
    return "。".join(parts) + "。"


def calculate_total_score(
    formal_score: float,
    technique_score: float,
    artistic_score: float,
    impression_score: float,
    weights=None
) -> float:
    """计算加权总分
    
    Args:
        formal_score: 形式合规得分 (0-1)
        technique_score: 对仗技术得分 (0-1)
        artistic_score: 艺术表现得分 (0-1)
        impression_score: AI印象得分 (0-1)
        weights: 权重字典，默认使用标准权重
        
    Returns:
        总分 (0-100)
    """
    if weights is None:
        weights = {
            'formal': 0.30,
            'technique': 0.30,
            'artistic': 0.30,
            'impression': 0.10
        }
    
    total = (
        weights['formal'] * formal_score +
        weights['technique'] * technique_score +
        weights['artistic'] * artistic_score +
        weights['impression'] * impression_score
    )
    return round(total * 100, 1)


def determine_grade(total_score: float) -> str:
    """根据总分确定评级
    
    Args:
        total_score: 总分 (0-100)
        
    Returns:
        评级字符串
    """
    grade_thresholds = [(90, "优秀"), (75, "良好"), (60, "及格"), (0, "不合格")]
    for threshold, grade in grade_thresholds:
        if total_score >= threshold:
            return grade
    return "不合格"
