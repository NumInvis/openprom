"""对联分析器统一接口 (Unified Analyzer Interface)

定义所有分析器的标准接口，实现：
1. 统一的输入输出格式
2. 可插拔的分析策略
3. 向后兼容的适配器模式
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """统一的分析结果数据结构"""
    upper: str
    lower: str
    
    # 核心评分（0-100）
    total_score: float = 0.0
    grade: str = ""
    
    # 分维度得分（0-1归一化）
    formal_score: float = 0.0
    technique_score: float = 0.0
    artistic_score: float = 0.0
    impression_score: float = 0.0
    
    # 详细信息
    comments: Dict[str, str] = None
    warnings: list = None
    score_breakdown: Dict[str, Any] = None
    computation_log: list = None
    
    # 扩展字段（各实现可自定义）
    extra_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.comments is None:
            self.comments = {}
        if self.warnings is None:
            self.warnings = []
        if self.score_breakdown is None:
            self.score_breakdown = {}
        if self.computation_log is None:
            self.computation_log = []
        if self.extra_data is None:
            self.extra_data = {}


class CoupletAnalyzerInterface(ABC):
    """对联分析器抽象基类"""
    
    @abstractmethod
    def analyze(self, upper: str, lower: str) -> AnalysisResult:
        """执行完整分析
        
        Args:
            upper: 上联
            lower: 下联
            
        Returns:
            AnalysisResult对象
        """
        pass
    
    @abstractmethod
    def get_analyzer_info(self) -> Dict[str, Any]:
        """获取分析器信息
        
        Returns:
            包含名称、版本、特性等信息的字典
        """
        pass


class DualAPIAnalyzerAdapter(CoupletAnalyzerInterface):
    """双API分析器的适配器（实现统一接口）"""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        from porm.core.dual_api_scorer import DualAPITechniqueScorer
        self._scorer = DualAPITechniqueScorer(api_key, base_url, model)
    
    def analyze(self, upper: str, lower: str) -> AnalysisResult:
        """调用双API系统进行分析"""
        dual_result = self._scorer.analyze(upper, lower)
        
        return AnalysisResult(
            upper=upper,
            lower=lower,
            
            total_score=dual_result.total_score,
            grade=dual_result.grade,
            
            formal_score=dual_result.formal_score,
            technique_score=dual_result.technique_score,
            artistic_score=dual_result.artistic_score,
            impression_score=dual_result.impression_score,
            
            comments=dual_result.comments,
            warnings=dual_result.warnings,
            score_breakdown=dual_result.score_breakdown,
            computation_log=dual_result.computation_log,
            
            extra_data={
                "first_impression_score": dual_result.first_impression_score,
                "llm_technique_score": dual_result.llm_technique_score,
                "llm_rhetoric_score": dual_result.llm_rhetoric_score,
                "special_attention": dual_result.special_attention,
                "final_technique_score": dual_result.final_technique_score,
                "pingze_score": dual_result.pingze_score
            }
        )
    
    def get_analyzer_info(self) -> Dict[str, Any]:
        return {
            "name": "Dual-API Technique Scorer",
            "version": "4.2.0",
            "type": "dual_api",
            "features": [
                "双阶段API调用",
                "加权评分",
                "特别注意机制",
                "NLP规则特征融合"
            ],
            "model": self._scorer.model
        }


def create_analyzer(api_key: str, base_url: str, model: str) -> CoupletAnalyzerInterface:
    """工厂函数：创建分析器实例
    
    当前默认返回DualAPI分析器。
    未来可根据配置选择不同的分析策略。
    
    Args:
        api_key: API密钥
        base_url: API基础URL
        model: 模型名称
        
    Returns:
        实现了CoupletAnalyzerInterface的分析器实例
    """
    return DualAPIAnalyzerAdapter(api_key, base_url, model)
