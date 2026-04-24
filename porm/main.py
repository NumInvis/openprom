"""PORM 命令行入口 (已弃用)

⚠️ 警告：CLI 模式已弃用，请使用 Web 界面访问 http://localhost:8000

提供对联评分、诗律检测、词牌检测等功能。
"""

import argparse
import os
import warnings
from typing import List, Optional

from porm.core.analyzer import analyze as analyze_couplet
from porm.engines.meter import match_shi, match_ci, find_best_shi, find_best_ci
from porm.utils.config import load_config as _load_config

warnings.warn(
    "CLI 模式已弃用，请使用 Web 界面：http://localhost:8000\n"
    "运行 python -m porm.api 启动 Web 服务",
    DeprecationWarning,
    stacklevel=2
)


def load_config() -> dict:
    """加载配置文件（委托给统一配置加载器）"""
    return _load_config()


def check_couplet(
    upper: str,
    lower: str,
    api_key: str,
    base_url: str,
    model: str,
    verbose: bool = True
):
    """检查对联并输出结果

    Args:
        upper: 上联
        lower: 下联
        api_key: LLM API密钥
        base_url: LLM API基础URL
        model: LLM模型名称
        verbose: 是否打印详细信息
    """
    result = analyze_couplet(upper, lower, api_key, base_url, model)

    if verbose:
        print("=" * 50)
        print(f"上联: {result.upper}")
        print(f"下联: {result.lower}")
        print("=" * 50)
        print("\n【各维度得分】")
        print(f"  形式合规 (30%): {result.formal_score * 100:.1f}分")
        print(f"    └─ 平仄得分: {result.pingze_score * 100:.1f}分")
        print(f"  对仗技术 (30%): {result.duizhang_score * 100:.1f}分")
        print(f"    ├─ NLP分析: {result.nlp_duizhang * 100:.1f}分")
        print(f"    └─ LLM辅助: {result.llm_duizhang * 100:.1f}分")
        print(f"  艺术表现 (30%): {result.artistic_score * 100:.1f}分")
        print(f"  AI印象   (10%): {result.impression_score * 100:.1f}分")
        print("-" * 50)
        print(f"【总分】 {result.total_score:.1f}分 【{result.grade}】")
        print("=" * 50)

        if result.warnings:
            print("\n【警告】")
            for warning in result.warnings:
                print(f"  ⚠ {warning}")

        if result.impression_reason:
            print(f"\n【AI印象】{result.impression_reason}")

        if result.artistic_analysis:
            print("\n【艺术表现分析】")
            analysis = result.artistic_analysis
            if "overall_comment" in analysis:
                print(f"  {analysis['overall_comment']}")
            for key in ["意境", "修辞", "文化", "语言", "创新"]:
                if key in analysis:
                    item = analysis[key]
                    print(f"  {key}: {item.get('score', 0)}分 - {item.get('comment', '')}")

    return result


def check_shi(lines: List[str], pattern_name: str = None, verbose: bool = True):
    """检查诗体格律

    Args:
        lines: 诗句列表
        pattern_name: 诗体名称，如"五律"，为None时自动匹配
        verbose: 是否打印详细信息
    """
    if pattern_name:
        result = match_shi(lines, pattern_name)
        if verbose:
            print(f"诗体: {pattern_name}")
            print(f"匹配率: {result.match_rate:.2%}")
            print(f"是否合格: {'是' if result.is_valid else '否'}")
            if result.errors:
                print(f"错误数: {len(result.errors)}")
                for err in result.errors[:5]:
                    if "pos" in err:
                        print(f"  第{err.get('line', 0)+1}句第{err['pos']+1}字 '{err['char']}': 应为{err['expected']}")
    else:
        results = find_best_shi(lines)
        if verbose:
            print("最佳匹配诗体:")
            for r in results[:3]:
                status = "✓" if r.is_valid else "✗"
                print(f"  {status} {r.pattern_name}: {r.match_rate:.2%}")
        result = results[0] if results else None

    return result


def check_ci(lines: List[str], pattern_name: str = None, verbose: bool = True):
    """检查词牌格律

    Args:
        lines: 词句列表
        pattern_name: 词牌名称，如"蝶恋花"，为None时自动匹配
        verbose: 是否打印详细信息
    """
    if pattern_name:
        result = match_ci(lines, pattern_name)
        if verbose:
            print(f"词牌: {pattern_name}")
            print(f"匹配率: {result.match_rate:.2%}")
            print(f"是否合格: {'是' if result.is_valid else '否'}")
    else:
        results = find_best_ci(lines)
        if verbose:
            print("最佳匹配词牌:")
            for r in results[:3]:
                status = "✓" if r.is_valid else "✗"
                print(f"  {status} {r.pattern_name}: {r.match_rate:.2%}")
        result = results[0] if results else None

    return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="PORM - 对联自动评分系统 v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
评分架构:
  - 形式合规 (30%): 平仄、字数、格律
  - 对仗技术 (30%): NLP语义分析 + LLM辅助判断
  - 艺术表现 (30%): LLM深度文学分析
  - AI印象   (10%): AI整体印象评分

示例:
  # 对联评分
  python -m porm.main couplet "春风化雨" "秋月寒霜"

  # 诗律检测
  python -m porm.main shi "白日依山尽" "黄河入海流" "欲穷千里目" "更上一层楼"

  # 词牌检测
  python -m porm.main ci "花褪残红青杏小" "燕子飞时" "绿水人家绕"

  # 列出可用模式
  python -m porm.main list shi
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # couplet 命令
    couplet_parser = subparsers.add_parser("couplet", help="对联评分")
    couplet_parser.add_argument("upper", help="上联")
    couplet_parser.add_argument("lower", help="下联")
    couplet_parser.add_argument("--api-key", help="LLM API密钥")
    couplet_parser.add_argument("--base-url", help="LLM API基础URL")
    couplet_parser.add_argument("--model", help="LLM模型名称")

    # shi 命令
    shi_parser = subparsers.add_parser("shi", help="诗律检测")
    shi_parser.add_argument("lines", nargs="+", help="诗句")
    shi_parser.add_argument("--pattern", "-p", help="指定诗体（如：五律、七律）")

    # ci 命令
    ci_parser = subparsers.add_parser("ci", help="词牌检测")
    ci_parser.add_argument("lines", nargs="+", help="词句")
    ci_parser.add_argument("--pattern", "-p", help="指定词牌（如：蝶恋花、浣溪沙）")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出可用模式")
    list_parser.add_argument("type", choices=["shi", "ci"], help="类型")

    args = parser.parse_args()

    if args.command == "couplet":
        # 加载配置
        config = load_config()

        # 优先级: 命令行参数 > 配置文件 > 环境变量
        api_key = args.api_key or config.get("api_key") or os.environ.get("PORM_API_KEY")
        base_url = args.base_url or config.get("base_url") or os.environ.get("PORM_BASE_URL")
        model = args.model or config.get("model") or os.environ.get("PORM_MODEL")

        if not api_key:
            print("错误: 未提供API密钥。请通过--api-key参数、config.json或PORM_API_KEY环境变量设置。")
            return
        if not base_url:
            print("错误: 未提供API基础URL。请通过--base-url参数、config.json或PORM_BASE_URL环境变量设置。")
            return
        if not model:
            print("错误: 未提供模型名称。请通过--model参数、config.json或PORM_MODEL环境变量设置。")
            return

        check_couplet(args.upper, args.lower, api_key, base_url, model)

    elif args.command == "shi":
        check_shi(args.lines, args.pattern)

    elif args.command == "ci":
        check_ci(args.lines, args.pattern)

    elif args.command == "list":
        from porm.data.loader import MeterPattern
        patterns = MeterPattern.get()
        if args.type == "shi":
            print("可用诗体:")
            for name in sorted(patterns.list_shi_patterns()):
                print(f"  - {name}")
        else:
            print("可用词牌:")
            for name in sorted(patterns.list_ci_patterns()):
                print(f"  - {name}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
