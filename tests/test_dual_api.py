"""双API技法评分系统 - 测试脚本

测试对联: 几孤风月 / 屡变星霜
"""

import json
import sys
from pathlib import Path


def load_config():
    """加载配置（从项目根目录）"""
    config_path = Path(__file__).resolve().parent.parent / "config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    print("="*70)
    print("       双API技法评分系统 - 测试运行")
    print("="*70)
    print()
    
    # 加载配置
    config = load_config()
    api_key = config["api_key"]
    base_url = config["base_url"]
    model = config["model"]
    
    # 测试对联
    upper = "几孤风月"
    lower = "屡变星霜"
    
    print(f"📝 测试对联:")
    print(f"   上联: {upper}")
    print(f"   下联: {lower}")
    print()
    
    # 导入双API评分器
    from porm.core.dual_api_scorer import analyze_dual_api
    
    print("🚀 启动双API分析...")
    print()
    
    try:
        result = analyze_dual_api(upper, lower, api_key, base_url, model)
        
        print("\n" + "="*70)
        print("                    📊 评分结果")
        print("="*70)
        
        print(f"\n🎯 最终评分: {result.total_score}/100 ({result.grade})")
        
        print(f"\n━━━ 技法评分明细（双API系统 - 优化版） ━━━")
        print(f"公式: BERT_归一化(60%) + LLM技法(20%) + LLM修辞(20%)")
        print(f"      [BERT使用句子级[CLS]编码 + Z-score+Sigmoid归一化]")
        print()
        
        breakdown = result.score_breakdown
        if breakdown and "components" in breakdown:
            components = breakdown["components"]
            
            bert_comp = components.get("bert_cosine", {})
            print(f"┌─ BERT余弦相似度 (权重60%):")
            print(f"│  编码方式: {result.bert_detailed_analysis.get('encoding_method', 'N/A')}")
            print(f"│  原始值: {bert_comp.get('raw_value', 0):.4f}")
            print(f"│  归一化值: {bert_comp.get('normalized_value', 0):.4f}")
            if "bert_details" in breakdown:
                bert_details = breakdown["bert_details"]
                print(f"│  归一化方法: {bert_details.get('normalization_method', 'N/A')}")
            print(f"│  贡献分: {bert_comp.get('contribution', 0)*100:.2f}")
            print()
            
            tech_comp = components.get("llm_technique", {})
            print(f"├─ LLM技法综合评价 (权重20%):")
            print(f"│  得分: {tech_comp.get('raw_value', 0)*100:.2f}/100")
            print(f"│  贡献分: {tech_comp.get('contribution', 0)*100:.2f}")
            print()
            
            rhet_comp = components.get("llm_rhetoric", {})
            print(f"└─ LLM修辞评价 (权重20%):")
            print(f"   得分: {rhet_comp.get('raw_value', 0)*100:.2f}/100")
            print(f"   贡献分: {rhet_comp.get('contribution', 0)*100:.2f}")
            print()
        
        print(f"★ 最终技法得分: {result.final_technique_score*100:.2f}/100")
        
        print(f"\n━━━ 其他维度 ━━━")
        print(f"形式合规: {result.formal_score*100:.2f}/100")
        print(f"艺术表现: {result.artistic_score*100:.2f}/100")
        print(f"第一印象: {result.impression_score*100:.2f}/100")
        
        if result.warnings:
            print(f"\n⚠️ 格律警告: {', '.join(result.warnings)}")
        
        print(f"\n━━━ 评价依据 ━━━")
        print(f"\n【第一印象评价】")
        print(result.comments.get("impression_comment", ""))
        
        print(f"\n【特别注意事项】（指导第二次分析）")
        if result.special_attention:
            for key, value in result.special_attention.items():
                print(f"  • {key}: {value}")
        
        print(f"\n【技法综合评价】")
        print(result.comments.get("technique_comment", ""))
        
        print(f"\n【艺术与修辞评价】")
        print(result.comments.get("artistic_comment", ""))
        
        print(f"\n【总体评语】")
        print(result.comments.get("overall_comment", ""))
        
        print(f"\n━━━ BERT逐字分析（前5组） ━━━")
        char_analysis = result.bert_detailed_analysis.get("char_level_analysis", [])
        for item in char_analysis[:5]:
            print(
                f"位置{item['position']}: '{item['upper_char']}' ↔ '{item['lower_char']}' "
                f"| 相似度: {item['cosine_similarity']:.4f} ({item['similarity_level']})"
            )
        
        print(f"\n═══════════════════════════════════════════════")
        print("                 完整计算日志")
        print("═══════════════════════════════════════════════\n")
        
        for log_entry in result.computation_log:
            print(log_entry)
        
        print("\n✅ 测试完成！")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
