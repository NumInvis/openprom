"""PORM API 全面功能测试脚本

测试对联："明天我会写出诗句吗" 对下联
验证优化后的完整调用链路：配置加载 → 分析器初始化 → 双API调用 → BERT融合 → 成本控制 → 结果输出
"""

import sys
import os
import time
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime


def separator(title=""):
    print("\n" + "=" * 70)
    if title:
        center = f"  {title}  "
        print(center.center(70, "="))
    print("=" * 70)


def test_section(name):
    print(f"\n{'─' * 70}")
    print(f"  ▶ {name}")
    print(f"{'─' * 70}")


def pass_fail(condition, detail=""):
    status = "✅ PASS" if condition else "❌ FAIL"
    if detail:
        print(f"     {status} — {detail}")
    else:
        print(f"     {status}")
    return condition


# ============================================================
# 测试结果收集器
# ============================================================
test_results = []


def record_test(category, name, passed, detail="", elapsed=0):
    test_results.append({
        "category": category,
        "name": name,
        "passed": passed,
        "detail": detail,
        "elapsed": round(elapsed, 3)
    })


# ============================================================
# 测试开始
# ============================================================
print("=" * 70)
print("  PORM v3.1 系统性优化后 - API全面功能测试报告")
print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

TOTAL_TESTS = 0
PASSED_TESTS = 0

# ---- 测试用例数据 ----
TEST_UPPER = "明天我会写出诗句吗"
TEST_LOWER = "今日君能吟就文章乎"

# ============================================================
# Phase 1: 模块导入与基础组件测试
# ============================================================
separator("Phase 1: 模块导入与基础组件测试")

test_section("1.1 核心模块导入")
t_start = time.time()
try:
    from porm.core.base_analyzer import (
        analyze_formal, generate_overall_comment,
        calculate_total_score, determine_grade
    )
    ok = True
    record_test("模块导入", "base_analyzer", True)
except Exception as e:
    ok = False
    record_test("模块导入", "base_analyzer", False, str(e))
if ok:
    PASSED_TESTS += 1
TOTAL_TESTS += 1
print(f"     ✅ base_analyzer 导入成功 ({time.time()-t_start:.3f}s)")

try:
    from porm.core.analyzer import CoupletAnalyzer, CoupletScore, analyze
    record_test("模块导入", "analyzer (兼容层)", True)
    PASSED_TESTS += 1
    TOTAL_TESTS += 1
    print(f"     ✅ analyzer (兼容层) 导入成功")
except Exception as e:
    record_test("模块导入", "analyzer (兼容层)", False, str(e))
    TOTAL_TESTS += 1
    print(f"     ❌ analyzer 导入失败: {e}")

try:
    from porm.core.dual_api_scorer import DualAPITechniqueScorer, DualAPIScore
    record_test("模块导入", "dual_api_scorer", True)
    PASSED_TESTS += 1
    TOTAL_TESTS += 1
    print(f"     ✅ dual_api_scorer 导入成功")
except Exception as e:
    record_test("模块导入", "dual_api_scorer", False, str(e))
    TOTAL_TESTS += 1
    print(f"     ❌ dual_api_scorer 导入失败: {e}")

test_section("1.2 基础设施模块导入")
modules_infra = [
    ("porm.infrastructure.config.settings", "Settings"),
    ("porm.infrastructure.config.prompt_config", "PromptConfigService"),
    ("porm.data.loader", "RhymeBook/MeterPattern"),
    ("porm.engines.pingze", "PingZeEngine"),
]
for mod_path, desc in modules_infra:
    try:
        __import__(mod_path)
        record_test("模块导入", desc, True)
        PASSED_TESTS += 1
        TOTAL_TESTS += 1
        print(f"     ✅ {desc} 导入成功")
    except Exception as e:
        record_test("模块导入", desc, False, str(e))
        TOTAL_TESTS += 1
        print(f"     ❌ {desc} 导入失败: {e}")

test_section("1.3 工具模块导入")
modules_utils = [
    ("porm.utils.json_parser", "JSON解析器(增强版)"),
    ("porm.utils.scoring", "评分工具"),
    ("porm.utils.config", "统一配置加载器"),
    ("porm.utils.common", "公共工具函数"),
]
for mod_path, desc in modules_utils:
    try:
        __import__(mod_path)
        record_test("模块导入", desc, True)
        PASSED_TESTS += 1
        TOTAL_TESTS += 1
        print(f"     ✅ {desc} 导入成功")
    except Exception as e:
        record_test("模块导入", desc, False, str(e))
        TOTAL_TESTS += 1
        print(f"     ❌ {desc} 导入失败: {e}")

# ============================================================
# Phase 2: 基础分析器单元测试（无需API）
# ============================================================
separator("Phase 2: 基础分析器单元测试（本地计算）")

test_section("2.1 形式分析 - 平仄检测")
t_start = time.time()
formal_score, pingze_score, warnings = analyze_formal(TEST_UPPER, TEST_LOWER)
elapsed = time.time() - t_start
print(f"     上联: 「{TEST_UPPER}」")
print(f"     下联: 「{TEST_LOWER}」")
print(f"     字数: 上={len(TEST_UPPER)}, 下={len(TEST_LOWER)}")
print(f"     形式得分: {formal_score:.4f}, 平仄得分: {pingze_score:.4f}")
print(f"     警告: {warnings if warnings else '无'}")

ok_len = len(TEST_UPPER) == len(TEST_LOWER)
record_test("形式分析", "字数相等检查", ok_len,
            f"上{len(TEST_UPPER)}字 vs 下{len(TEST_LOWER)}字")
if ok_len: PASSED_TESTS += 1
TOTAL_TESTS += 1

ok_range = 0 <= formal_score <= 1
record_test("形式分析", "得分范围[0,1]", ok_range, f"score={formal_score:.4f}")
if ok_range: PASSED_TESTS += 1
TOTAL_TESTS += 1

record_test("形式分析", "响应时间<100ms", elapsed < 0.1, f"{elapsed*1000:.1f}ms")
if elapsed < 0.1: PASSED_TESTS += 1
TOTAL_TESTS += 1

test_section("2.2 句法特征 - 动态POS估算（修复后）")
from porm.core.fusion_engine import FeatureExtractor
from collections import OrderedDict
fe = FeatureExtractor.__new__(FeatureExtractor)
fe._char_embedding_cache = OrderedDict()
fe._sentence_embedding_cache = OrderedDict()
fe._char_cache_max_size = 10000
fe._sentence_cache_max_size = 1000

t_start = time.time()
syntactic = fe.extract_syntactic_features(TEST_UPPER, TEST_LOWER)
elapsed = time.time() - t_start

pos_rate = syntactic["pos_match_rate"]
struct_para = syntactic["structure_parallelism"]
congruence = syntactic["syntactic_congruence"]

print(f"     POS匹配率: {pos_rate:.4f}")
print(f"     结构平行度: {struct_para:.4f}")
print(f"     句法一致性: {congruence:.4f}")

ok_not_hardcoded = pos_rate != 0.7 or len(TEST_UPPER) != len(TEST_LOWER)
record_test("句法特征", "非硬编码值(P0修复验证)", ok_not_hardcoded,
            f"pos_match={pos_rate:.4f} (原bug: 恒为0.7)")
if ok_not_hardcoded: PASSED_TESTS += 1
TOTAL_TESTS += 1

ok_pos_range = 0 <= pos_rate <= 1
record_test("句法特征", "POS匹配率范围[0,1]", ok_pos_range)
if ok_pos_range: PASSED_TESTS += 1
TOTAL_TESTS += 1

ok_struct_range = 0 <= struct_para <= 1
record_test("句法特征", "结构平行度范围[0,1]", ok_struct_range)
if ok_struct_range: PASSED_TESTS += 1
TOTAL_TESTS += 1

syntactic_uneven = fe.extract_syntactic_features("短", "很长很长的句子")
ok_uneven_zero = syntactic_uneven["pos_match_rate"] == 0.0
record_test("句法特征", "不等长返回0", ok_uneven_zero,
            f"不等长pos_match={syntactic_uneven['pos_match_rate']}")
if ok_uneven_zero: PASSED_TESTS += 1
TOTAL_TESTS += 1

test_section("2.3 JSON解析增强测试")
from porm.utils.json_parser import (
    parse_llm_json_response, safe_parse_llm_response, JSONParseError
)

json_tests = [
    ("纯JSON", '{"score": 85}', {'score': 85}),
    ("Markdown包裹", '```\n{"key": "val"}\n```', {'key': 'val'}),
    ("带前缀文字", '结果是：{"a": 1}', {'a': 1}),
    ("嵌套JSON", '{"outer": {"inner": 42}}', {'outer': {'inner': 42}}),
]

for name, input_str, expected_partial in json_tests:
    try:
        result = parse_llm_json_response(input_str)
        ok = isinstance(result, dict) and len(result) > 0
        record_test("JSON解析", name, ok, f"result={result}")
        if ok: PASSED_TESTS += 1
    except Exception as e:
        record_test("JSON解析", name, False, str(e))
    TOTAL_TESTS += 1
    status = "✅" if ok else "❌"
    print(f"     {status} {name}: {input_str[:40]}...")

fallback_result = safe_parse_llm_response(
    "这不是JSON内容",
    required_fields={"score": 50, "reason": "默认"}
)
ok_fallback = fallback_result.get("score") == 50
record_test("JSON解析", "安全解析降级(无效输入)", ok_fallback,
            f"score={fallback_result.get('score')}")
if ok_fallback: PASSED_TESTS += 1
TOTAL_TESTS += 1
print(f"     {'✅' if ok_fallback else '❌'} 安全解析降级: 无效输入→默认值score=50")

test_section("2.4 接口实现验证")
try:
    from porm.core.analyzer_interface import CoupletAnalyzerInterface
    from porm.core.analyzer import CoupletAnalyzer
    
    is_implement = issubclass(CoupletAnalyzer, CoupletAnalyzerInterface)
    record_test("接口实现", "CoupletAnalyzer实现CoupletAnalyzerInterface", is_implement)
    if is_implement: PASSED_TESTS += 1
    TOTAL_TESTS += 1
    print(f"     {'✅' if is_implement else '❌'} CoupletAnalyzer → CoupletAnalyzerInterface ✓")
except Exception as e:
    record_test("接口实现", "CoupletAnalyzer实现CoupletAnalyzerInterface", False, str(e))
    TOTAL_TESTS += 1
    print(f"     ❌ 接口验证失败: {e}")

# ============================================================
# Phase 3: 完整API集成测试（需要网络+API Key）
# ============================================================
separator("Phase 3: 完整API集成测试（双API + BERT融合）")

test_section("3.1 加载API配置")
from porm.utils.config import get_project_root
config_path = str(get_project_root() / "config.json")
api_key, base_url, model = "", "", ""

if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        api_key = cfg.get("api_key", "")
        base_url = cfg.get("base_url", "")
        model = cfg.get("model", "")
        
        has_key = bool(api_key)
        has_url = bool(base_url)
        has_model = bool(model)
        
        record_test("API配置", "config.json存在且可读取", True)
        PASSED_TESTS += 1
        TOTAL_TESTS += 1
        
        record_test("API配置", "api_key已配置", has_key, f"{'***' + api_key[-6:] if has_key else '未设置'}")
        if has_key: PASSED_TESTS += 1
        TOTAL_TESTS += 1
        
        record_test("API配置", "base_url已配置", has_url, base_url)
        if has_url: PASSED_TESTS += 1
        TOTAL_TESTS += 1
        
        record_test("API配置", "model已配置", has_model, model)
        if has_model: PASSED_TESTS += 1
        TOTAL_TESTS += 1
        
        print(f"     ✅ 配置加载成功:")
        print(f"        API Key: ***{api_key[-6:] if api_key else 'N/A'}")
        print(f"        Base URL: {base_url}")
        print(f"        Model: {model}")
    except Exception as e:
        record_test("API配置", "config.json读取", False, str(e))
        TOTAL_TESTS += 1
        print(f"     ❌ 配置文件读取失败: {e}")
else:
    record_test("API配置", "config.json存在", False, "文件不存在")
    TOTAL_TESTS += 1
    print(f"     ❌ config.json 不存在于 {config_path}")

if not all([api_key, base_url, model]):
    print("\n     ⚠️  API配置不完整，跳过在线API测试")
    print("     请确保 config.json 包含 api_key, base_url, model 字段")
else:
    test_section("3.2 DualAPITechniqueScorer 完整分析流程")
    
    print(f"\n     📝 待评对联:")
    print(f"        上联: 「{TEST_UPPER}」({len(TEST_UPPER)}字)")
    print(f"        下联: 「{TEST_LOWER}」({len(TEST_LOWER)}字)")
    
    t_total_start = time.time()
    
    try:
        scorer = DualAPITechniqueScorer(api_key, base_url, model)
        record_test("API集成", "Scorer初始化", True, f"model={model}")
        PASSED_TESTS += 1
        TOTAL_TESTS += 1
        print(f"     ✅ Scorer 初始化成功")
        
        print(f"\n     🚀 开始完整分析流程...")
        result = scorer.analyze(TEST_UPPER, TEST_LOWER)
        t_total = time.time() - t_total_start
        
        print(f"\n     {'=' * 60}")
        print(f"     📊 分析结果 (耗时 {t_total:.2f}s)")
        print(f"     {'=' * 60}")
        
        result_checks = [
            ("返回类型为DualAPIScore", isinstance(result, DualAPIScore)),
            ("formal_score存在且在[0,1]", hasattr(result, 'formal_score') and 0 <= result.formal_score <= 1),
            ("technique_score存在且在[0,1]", hasattr(result, 'technique_score') and 0 <= result.technique_score <= 1),
            ("artistic_score存在且在[0,1]", hasattr(result, 'artistic_score') and 0 <= result.artistic_score <= 1),
            ("impression_score存在且在[0,1]", hasattr(result, 'impression_score') and 0 <= result.impression_score <= 1),
            ("total_score存在且在[0,100]", hasattr(result, 'total_score') and 0 <= result.total_score <= 100),
            ("grade为有效评级", hasattr(result, 'grade') and result.grade in ["优秀", "良好", "及格", "不合格"]),
            ("comments字典非空", hasattr(result, 'comments') and isinstance(result.comments, dict) and len(result.comments) > 0),
            ("warnings列表存在", hasattr(result, 'warnings') and isinstance(result.warnings, list)),
            ("bert_similarity有值", hasattr(result, 'bert_cosine_similarity') and result.bert_cosine_similarity is not None),
        ]
        
        for check_name, check_cond in result_checks:
            record_test("API结果验证", check_name, check_cond)
            if check_cond: PASSED_TESTS += 1
            TOTAL_TESTS += 1
            print(f"     {'✅' if check_cond else '❌'} {check_name}")
        
        print(f"\n     ┌────────────────────────────────────────┐")
        print(f"     │         各维度评分详情                  │")
        print(f"     ├────────────────────────────────────────┤")
        print(f"     │  形式合规:   {result.formal_score*100:>6.1f}分 (权重30%)  │")
        print(f"     │    └平仄:    {result.pingze_score*100:>6.1f}分           │")
        print(f"     │  对仗技术:   {result.technique_score*100:>6.1f}分 (权重30%)  │")
        print(f"     │    ├BERT:    {result.bert_cosine_similarity*100:>6.1f}分 (60%)│")
        print(f"     │    ├技法LLM: {result.llm_technique_score*100:>6.1f}分 (20%)│")
        print(f"     │    └修辞LLM: {result.llm_rhetoric_score*100:>6.1f}分 (20%)│")
        print(f"     │  艺术表现:   {result.artistic_score*100:>6.1f}分 (权重30%)  │")
        print(f"     │  AI印象:     {result.impression_score*100:>6.1f}分 (权重10%)  │")
        print(f"     ├────────────────────────────────────────┤")
        print(f"     │  【总分】{result.total_score:>6.1f}分 【{result.grade}】      │")
        print(f"     └────────────────────────────────────────┘")
        
        if result.warnings:
            print(f"\n     ⚠️  警告: {', '.join(result.warnings)}")
        
        print(f"\n     💬 AI第一印象:")
        imp_reason = getattr(result, 'first_impression_reason', '')
        if imp_reason:
            print(f"        得分: {result.impression_score*100:.1f}分")
            print(f"        理由: {imp_reason[:100]}...")
        
        print(f"\n     📝 技法评价:")
        tech_comment = result.comments.get('technique_comment', 'N/A')
        print(f"        {tech_comment[:120]}...")
        
        print(f"\n     🎨 艺术/修辞评价:")
        art_comment = result.comments.get('artistic_comment', 'N/A')
        print(f"        {art_comment[:120]}...")
        
        print(f"\n     📋 总体评价:")
        overall_comment = result.comments.get('overall_comment', 'N/A')
        print(f"        {overall_comment}")
        
    except Exception as e:
        t_total = time.time() - t_total_start
        record_test("API集成", "完整分析流程执行", False, f"{type(e).__name__}: {e}")
        TOTAL_TESTS += 1
        print(f"     ❌ 分析过程出错 ({t_total:.2f}s):")
        traceback.print_exc()

# ============================================================
# Phase 4: 兼容层测试
# ============================================================
separator("Phase 4: 兼容层(CoupletAnalyzer)测试")

if api_key and base_url and model:
    test_section("4.1 CoupletAnalyzer 兼容层包装 + 接口验证")
    try:
        compat_analyzer = CoupletAnalyzer(api_key, base_url, model)
        compat_result = compat_analyzer.analyze(TEST_UPPER, TEST_LOWER)
        
        # 验证接口方法可用
        info = compat_analyzer.get_analyzer_info()
        has_info = isinstance(info, dict) and "name" in info
        
        # 验证转换方法可用
        core_result = compat_result.to_analysis_result()
        can_convert = isinstance(core_result, type(compat_result)) or hasattr(core_result, 'total_score')
        
        compat_checks = [
            ("返回CoupletScore对象", isinstance(compat_result, CoupletScore)),
            ("upper字段正确", compat_result.upper == TEST_UPPER),
            ("lower字段正确", compat_result.lower == TEST_LOWER),
            ("total_score有效", 0 <= compat_result.total_score <= 100),
            ("grade有效", compat_result.grade in ["优秀","良好","及格","不合格"]),
            ("实现了get_analyzer_info()", has_info),
            ("支持to_analysis_result()转换", can_convert),
        ]
        
        for check_name, check_cond in compat_checks:
            record_test("兼容层", check_name, check_cond)
            if check_cond: PASSED_TESTS += 1
            TOTAL_TESTS += 1
            print(f"     {'✅' if check_cond else '❌'} {check_name}")
        
        print(f"\n     兼容层结果: total={compat_result.total_score}, grade={compat_result.grade}")
        print(f"     接口信息: {info.get('name', 'N/A')} v{info.get('version', 'N/A')}")
        
    except Exception as e:
        record_test("兼容层", "CoupletAnalyzer执行", False, str(e))
        TOTAL_TESTS += 1
        print(f"     ❌ 兼容层测试失败: {e}")

# ============================================================
# 测试总结
# ============================================================
separator("测试总结报告")

pass_rate = (PASSED_TESTS / TOTAL_TESTS * 100) if TOTAL_TESTS > 0 else 0

print(f"""
  ┌──────────────────────────────────────────────────────┐
  │                  测试结果汇总                         │
  ├──────────────────────────────────────────────────────┤
  │  测试总数:    {TOTAL_TESTS:>4}                                  │
  │  通过数量:    {PASSED_TESTS:>4}                                  │
  │  失败数量:    {TOTAL_TESTS-PASSED_TESTS:>4}                                  │
  │  通过率:      {pass_rate:>5.1f}%                                │
  ├──────────────────────────────────────────────────────┤
  │  测试对联:    「{TEST_UPPER}」                          │
  │              「{TEST_LOWER}」                        │
  │  API模型:     {model or '(未配置)':<16}                       │
  │  测试时间:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}              │
  └──────────────────────────────────────────────────────┘
""")

if pass_rate >= 90:
    print(f"  🏆 评级: 优秀 ({pass_rate:.0f}% 通过) — 系统运行正常，所有核心功能可用")
elif pass_rate >= 70:
    print(f"  👍 评级: 良好 ({pass_rate:.0f}% 通过) — 主要功能正常，部分需关注")
elif pass_rate >= 50:
    print(f"  ⚠️ 评级: 及格 ({pass_rate:.0f}% 通过) — 存在明显问题，建议排查")
else:
    print(f"  ❌ 评级: 不合格 ({pass_rate:.0f}% 通过) — 存在严重问题，需立即修复")

print(f"\n  详细测试结果清单:")
print(f"  {'序号':>4s}  {'类别':<12s}  {'测试项':<35s}  {'结果':<6s}  {'详情'}")
print(f"  {'-'*4}  {'-'*12}  {'-'*35}  {'-'*6}  {'-'*25}")

for i, r in enumerate(test_results, 1):
    status = "PASS" if r["passed"] else "FAIL"
    detail = (r["detail"] or "")[:30]
    print(f"  {i:>4d}  {r['category']:<12s}  {r['name']:<35s}  {status:<6s}  {detail}")

print(f"\n{'='*70}")
print(f"  测试完成。")
print(f"{'='*70}")
