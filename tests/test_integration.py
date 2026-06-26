"""OpenPROM 集成测试 v4.2.0"""

from openprom.infrastructure.database import get_db_manager
from openprom.infrastructure.cache import get_cache_service
from openprom.infrastructure.logging import setup_logging
from openprom.utils.env_config import get_config
from openprom.utils.scoring import normalize_score, calculate_weighted_score


def test_database():
    """测试数据库"""
    stats = get_db_manager().get_statistics()
    assert isinstance(stats, dict), "统计信息应为字典"
    assert "total_analyses" in stats, "统计信息应包含 total_analyses"


def test_cache():
    """测试缓存服务"""
    stats = get_cache_service().get_stats()
    assert isinstance(stats, dict), "缓存状态应为字典"
    assert "enabled" in stats, "缓存状态应包含 enabled"

    if stats["enabled"]:
        get_cache_service().set("test", "key1", {"value": "test123"})
        result = get_cache_service().get("test", "key1")
        assert result == {"value": "test123"}, "缓存读写失败"


def test_logging():
    """测试日志服务"""
    logger = setup_logging("test")
    logger.info("测试日志消息")
    assert logger is not None, "日志初始化失败"


def test_env_config():
    """测试环境配置"""
    config = get_config()
    assert "model" in config, "配置缺少 model"
    assert "cache_enabled" in config, "配置缺少 cache_enabled"
    assert "log_level" in config, "配置缺少 log_level"


def test_scoring():
    """测试评分函数"""
    result1 = normalize_score(80, max_score=100)
    assert result1 == 0.8, f"归一化结果不正确: {result1}"

    scores = [80, 90, 70]
    weights = [0.5, 0.3, 0.2]
    result2 = calculate_weighted_score(scores, weights)
    assert 0 <= result2 <= 100, f"加权平均结果超出范围: {result2}"


def test_engines():
    """测试引擎"""
    from openprom.engines.pingze import get_sequence
    from openprom.engines.meter import get_engine
    from openprom.data.loader import MeterPattern

    seq = get_sequence("春风化雨")
    assert isinstance(seq, list), "平仄序列应为列表"

    patterns = MeterPattern.get()
    assert len(patterns.list_shi_patterns()) > 0, "诗体模板不应为空"

    engine = get_engine()
    result = engine.find_best_shi(["春风化雨"], top_k=1)
    assert result is not None, "格律匹配不应返回 None"


def test_api_module():
    """测试 API 模块"""
    from openprom.api import app
    from openprom.routers.common import CoupletRequest

    assert app.title == "OpenPROM API", f"API 标题错误: {app.title}"
    assert len(app.routes) > 0, "路由不应为空"

    req = CoupletRequest(upper="测试", lower="测试", stream=False)
    assert req.upper == "测试", "CoupletRequest upper 不正确"
    assert req.lower == "测试", "CoupletRequest lower 不正确"


def test_core_modules():
    """测试核心模块"""
    from openprom.core.saddle_engineering import SaddleEngineering
    from openprom.core.base_analyzer import analyze_formal

    formal_score, pingze_score, warnings = analyze_formal("春风", "秋雨")
    assert 0 <= formal_score <= 1, f"formal_score 超出范围: {formal_score}"
    assert 0 <= pingze_score <= 1, f"pingze_score 超出范围: {pingze_score}"
    # formal_score = 0.5*length + 0.3*pingze + 0.2*structure, should differ from pingze
    assert formal_score != pingze_score, (
        f"formal_score({formal_score}) 应与 pingze_score({pingze_score}) 不同"
    )

    saddle = SaddleEngineering()
    assert saddle._strict_mode is False, "默认应为非严格模式"
    assert saddle._max_violations == 3, "默认最大违规数应为 3"
