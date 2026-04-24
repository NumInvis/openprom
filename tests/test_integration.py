#!/usr/bin/env python3
"""PORM 集成测试脚本"""

from porm.infrastructure.database import db_manager, CoupletAnalysis
from porm.infrastructure.cache import cache_service
from porm.infrastructure.logging import setup_logging
from porm.utils.env_config import get_config
from porm.utils.scoring import normalize_cosine_similarity, normalize_zscore_sigmoid, calculate_weighted_score


def test_database():
    """测试数据库"""
    print('=== 数据库测试 ===')
    stats = db_manager.get_statistics()
    print(f'统计信息：{stats}')
    print('[OK] 数据库正常')
    return True


def test_cache():
    """测试缓存服务"""
    print('\n=== 缓存服务测试 ===')
    stats = cache_service.get_stats()
    print(f'缓存状态：enabled={stats["enabled"]}, redis_connected={stats["redis_connected"]}')
    
    if stats['enabled']:
        cache_service.set('test', 'key1', {'value': 'test123'})
        result = cache_service.get('test', 'key1')
        print(f'缓存读写：{result}')
        assert result == {'value': 'test123'}, '缓存读写失败'
    else:
        print('缓存未启用，跳过读写测试')
    
    print(f'缓存统计：{cache_service.get_stats()}')
    print('[OK] 缓存服务正常')
    return True


def test_logging():
    """测试日志服务"""
    print('\n=== 日志服务测试 ===')
    logger = setup_logging('test')
    logger.info('测试日志消息')
    logger.debug('调试消息')
    logger.warning('警告消息')
    print('[OK] 日志服务正常')
    return True


def test_env_config():
    """测试环境配置"""
    print('\n=== 环境配置测试 ===')
    config = get_config()
    print(f'模型：{config["model"]}')
    print(f'缓存启用：{config["cache_enabled"]}')
    print(f'日志级别：{config["log_level"]}')
    assert 'model' in config, '配置缺少 model'
    print('[OK] 环境配置正常')
    return True


def test_scoring():
    """测试评分函数"""
    print('\n=== 评分函数测试 ===')
    
    # 测试余弦相似度归一化
    result1 = normalize_cosine_similarity(0.6)
    print(f'normalize_cosine_similarity(0.6) = {result1:.4f}')
    assert 0 <= result1 <= 1, '归一化结果超出范围'
    
    result2 = normalize_cosine_similarity(-0.5)
    print(f'normalize_cosine_similarity(-0.5) = {result2:.4f}')
    assert 0 <= result2 <= 1, '归一化结果超出范围'
    
    # 测试 Z-score 归一化
    result3 = normalize_zscore_sigmoid(0.5)
    print(f'normalize_zscore_sigmoid(0.5) = {result3:.4f}')
    assert 0 <= result3 <= 1, '归一化结果超出范围'
    
    # 测试加权平均
    scores = [80, 90, 70]
    weights = [0.5, 0.3, 0.2]
    result4 = calculate_weighted_score(scores, weights)
    print(f'calculate_weighted_score([80,90,70], [0.5,0.3,0.2]) = {result4:.2f}')
    assert 0 <= result4 <= 100, '加权平均结果超出范围'
    
    print('[OK] 评分函数正常')
    return True


def test_engines():
    """测试引擎"""
    print('\n=== 引擎测试 ===')
    
    from porm.engines.pingze import get_sequence
    from porm.engines.meter import MeterEngine
    from porm.data.loader import MeterPattern
    
    # 测试平仄检测
    seq = get_sequence("春风化雨")
    print(f'平仄序列 ("春风化雨"): {seq}')
    
    # 测试格律引擎
    patterns = MeterPattern.get()
    print(f'诗体数量：{len(patterns.list_shi_patterns())}')
    print(f'词牌数量：{len(patterns.list_ci_patterns())}')
    
    print('[OK] 引擎正常')
    return True


def test_api_module():
    """测试 API 模块"""
    print('\n=== API 模块测试 ===')
    
    from porm.api import app, CoupletRequest, MeterRequest
    
    print(f'API 名称：{app.title}')
    print(f'API 版本：{app.version}')
    print(f'路由数量：{len(app.routes)}')
    
    # 测试请求模型
    req = CoupletRequest(upper="测试", lower="测试", stream=False)
    print(f'CoupletRequest: upper={req.upper}, lower={req.lower}')
    
    print('[OK] API 模块正常')
    return True


def test_core_modules():
    """测试核心模块"""
    print('\n=== 核心模块测试 ===')
    
    from porm.core.fusion_engine import FusionEngine, FeatureExtractor
    from porm.core.dual_api_scorer import DualAPITechniqueScorer
    from porm.core.saddle_engineering import SaddleEngineering
    
    print('FusionEngine: [OK]')
    print('DualAPITechniqueScorer: [OK]')
    print('SaddleEngineering: [OK]')
    
    print('[OK] 核心模块正常')
    return True


def main():
    """运行所有测试"""
    print('=' * 60)
    print('PORM v4.1.0 集成测试')
    print('=' * 60)
    
    tests = [
        ('数据库', test_database),
        ('缓存', test_cache),
        ('日志', test_logging),
        ('环境配置', test_env_config),
        ('评分函数', test_scoring),
        ('引擎', test_engines),
        ('API 模块', test_api_module),
        ('核心模块', test_core_modules),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f'[FAIL] {name} 测试失败：{str(e)}')
            failed += 1
    
    print('\n' + '=' * 60)
    print(f'测试结果：{passed} 通过，{failed} 失败')
    print('=' * 60)
    
    if failed == 0:
        print('[SUCCESS] 所有测试通过')
    else:
        print(f'[FAILED] {failed} 个测试失败')
    
    return failed == 0


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
