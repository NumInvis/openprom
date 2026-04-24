"""通用工具函数

提取各模块中重复使用的公共逻辑。
"""


def classify_similarity_level(sim: float) -> str:
    """分类相似度等级
    
    在 dual_api_scorer.py 和 fusion_engine.py 中均有使用，
    统一提取到此处消除重复。
    
    Args:
        sim: 相似度值 (0-1)
        
    Returns:
        等级字符串: 极高/高/中等/低/极低
    """
    if sim >= 0.9:
        return "极高"
    elif sim >= 0.7:
        return "高"
    elif sim >= 0.5:
        return "中等"
    elif sim >= 0.3:
        return "低"
    else:
        return "极低"
