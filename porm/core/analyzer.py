"""对联分析器 - 兼容层（Compatibility Layer）

已统一为 DualAPITechniqueScorer 实现。
本模块保留为向后兼容的薄包装层，同时实现 CoupletAnalyzerInterface 统一接口。
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field

from porm.core.analyzer_interface import CoupletAnalyzerInterface, AnalysisResult
from porm.core.dual_api_scorer import DualAPITechniqueScorer


@dataclass
class CoupletScore:
    """对联评分结果（兼容旧接口）
    
    保留供外部使用者直接引用。
    新代码推荐使用 AnalysisResult（来自 analyzer_interface）。
    """
    upper: str
    lower: str
    
    formal_score: float = 0.0
    technique_score: float = 0.0
    artistic_score: float = 0.0
    impression_score: float = 0.0
    
    pingze_score: float = 0.0
    meter_violations: List[str] = field(default_factory=list)
    
    llm_technique: Dict[str, Any] = field(default_factory=dict)
    llm_artistic: Dict[str, Any] = field(default_factory=dict)
    llm_impression: Dict[str, Any] = field(default_factory=dict)
    
    total_score: float = 0.0
    grade: str = ""
    
    technique_comment: str = ""
    artistic_comment: str = ""
    impression_comment: str = ""
    overall_comment: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_analysis_result(self) -> AnalysisResult:
        """转换为统一接口的 AnalysisResult 格式"""
        return AnalysisResult(
            upper=self.upper,
            lower=self.lower,
            total_score=self.total_score,
            grade=self.grade,
            formal_score=self.formal_score,
            technique_score=self.technique_score,
            artistic_score=self.artistic_score,
            impression_score=self.impression_score,
            comments={
                "technique_comment": self.technique_comment,
                "artistic_comment": self.artistic_comment,
                "impression_comment": self.impression_comment,
                "overall_comment": self.overall_comment,
            },
            warnings=self.warnings,
            extra_data={
                "pingze_score": self.pingze_score,
                "meter_violations": self.meter_violations,
                "llm_technique": self.llm_technique,
                "llm_artistic": self.llm_artistic,
                "llm_impression": self.llm_impression,
            },
        )


class CoupletAnalyzer(CoupletAnalyzerInterface):
    """对联分析器（兼容层 - 委托给DualAPITechniqueScorer）
    
    实现 CoupletAnalyzerInterface 统一接口，同时保留向后兼容的 CoupletScore 返回类型。
    内部实现统一使用双API评分系统。
    """
    
    WEIGHTS = {
        'formal': 0.30,
        'technique': 0.30,
        'artistic': 0.30,
        'impression': 0.10
    }
    
    GRADE_THRESHOLDS = [
        (90, "优秀"),
        (75, "良好"),
        (60, "及格"),
        (0, "不合格")
    ]
    
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._scorer = None
    
    def _get_scorer(self):
        if self._scorer is None:
            self._scorer = DualAPITechniqueScorer(
                self.api_key, self.base_url, self.model
            )
        return self._scorer
    
    def analyze(self, upper: str, lower: str) -> CoupletScore:
        """完整分析流程（委托给双API系统）
        
        返回 CoupletScore 以保持向后兼容。
        如需统一格式，可调用 result.to_analysis_result() 转换。
        """
        scorer = self._get_scorer()
        dual_result = scorer.analyze(upper, lower)
        
        # 转换为兼容格式
        result = CoupletScore(upper=upper, lower=lower)
        
        result.formal_score = dual_result.formal_score
        result.pingze_score = dual_result.pingze_score
        result.warnings = dual_result.warnings
        result.meter_violations = dual_result.warnings
        
        result.llm_technique = dual_result.llm_technique_evaluation
        result.llm_artistic = dual_result.llm_rhetoric_evaluation
        result.llm_impression = {
            "score": dual_result.first_impression_score * 100,
            "reason": dual_result.first_impression_reason,
            "special_attention": dual_result.special_attention
        }
        
        result.technique_score = dual_result.technique_score
        result.artistic_score = dual_result.artistic_score
        result.impression_score = dual_result.impression_score
        
        result.total_score = dual_result.total_score
        result.grade = dual_result.grade
        
        result.technique_comment = dual_result.comments.get("technique_comment", "")
        result.artistic_comment = dual_result.comments.get("artistic_comment", "")
        result.impression_comment = dual_result.comments.get("impression_comment", "")
        result.overall_comment = dual_result.comments.get("overall_comment", "")
        
        return result

    def get_analyzer_info(self) -> Dict[str, Any]:
        """获取分析器信息（CoupletAnalyzerInterface 实现）"""
        return {
            "name": "CoupletAnalyzer (Compatibility)",
            "version": "4.2.0",
            "type": "compatibility_layer",
            "description": "向后兼容包装层，内部委托给 DualAPITechniqueScorer",
            "features": [
                "向后兼容 CoupletScore 返回类型",
                "支持 to_analysis_result() 转换为统一格式",
                "委托双API评分系统",
            ],
            "model": self.model,
            "note": "新代码建议使用 create_analyzer() 获取 DualAPIAnalyzerAdapter",
        }


def analyze(upper: str, lower: str, api_key: str, base_url: str, model: str) -> CoupletScore:
    """便捷函数（向后兼容）"""
    return CoupletAnalyzer(api_key, base_url, model).analyze(upper, lower)
