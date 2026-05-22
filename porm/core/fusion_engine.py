"""NLP-LLM 融合引擎

版本：4.2.0

功能：
    - 特征提取（句法、韵律、统计）
    - 加权融合与贝叶斯融合
    - 评分算法实现
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import logging

logger = logging.getLogger(__name__)


class FusionStrategy(Enum):
    """融合策略"""
    WEIGHTED_AVERAGE = auto()
    BAYESIAN_FUSION = auto()


@dataclass
class NLPFeatures:
    """NLP 特征向量（纯规则提取，无模型依赖）"""
    pos_match_rate: float = 0.0
    structure_parallelism: float = 0.0
    syntactic_congruence: float = 0.0
    tonal_pattern_score: float = 0.0
    rhythm_harmony: float = 0.0
    char_overlap_ratio: float = 0.0
    length_balance: float = 0.0

    def to_vector(self) -> np.ndarray:
        return np.array([
            self.pos_match_rate,
            self.structure_parallelism,
            self.syntactic_congruence,
            self.tonal_pattern_score,
            self.rhythm_harmony,
            self.char_overlap_ratio,
            self.length_balance
        ])


@dataclass
class LLMOutput:
    """LLM 输出"""
    raw_score: float = 0.0
    confidence: float = 0.0
    reasoning: str = ""
    detailed_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FusionResult:
    """融合结果"""
    final_score: float = 0.0
    nlp_contribution: float = 0.0
    llm_contribution: float = 0.0
    fusion_confidence: float = 0.0
    decision_basis: List[str] = field(default_factory=list)
    feature_importance: Dict[str, float] = field(default_factory=dict)


class FeatureExtractor:
    """特征提取器（纯规则，无模型依赖）"""

    def extract_syntactic_features(self, upper: str, lower: str) -> Dict[str, float]:
        """提取句法特征（jieba分词+词性标注，降级为字符分类）"""
        if len(upper) != len(lower) or len(upper) == 0:
            return {"pos_match_rate": 0.0, "structure_parallelism": 0.0, "syntactic_congruence": 0.0}

        try:
            import jieba.posseg as pseg
            u_pos = list(pseg.cut(upper))
            l_pos = list(pseg.cut(lower))

            u_char_pos = []
            for word, flag in u_pos:
                for _ in word:
                    u_char_pos.append(flag[0])

            l_char_pos = []
            for word, flag in l_pos:
                for _ in word:
                    l_char_pos.append(flag[0])

            if len(u_char_pos) == len(l_char_pos) and len(u_char_pos) > 0:
                pos_match = sum(1 for a, b in zip(u_char_pos, l_char_pos) if a == b) / len(u_char_pos)
            else:
                pos_match = 0.0

            u_words = len(u_pos)
            l_words = len(l_pos)
            structure_parallel = 1.0 - abs(u_words - l_words) / max(u_words, l_words, 1)

            return {
                "pos_match_rate": round(pos_match, 4),
                "structure_parallelism": round(structure_parallel, 4),
                "syntactic_congruence": round((pos_match + structure_parallel) / 2, 4)
            }

        except ImportError:
            match_count = sum(
                1 for u_char, l_char in zip(upper, lower)
                if self._classify_char(u_char) == self._classify_char(l_char)
            )
            pos_match = match_count / len(upper)
            return {
                "pos_match_rate": round(pos_match, 4),
                "structure_parallelism": round(pos_match, 4),
                "syntactic_congruence": round(pos_match, 4)
            }

    def _classify_char(self, char: str) -> str:
        cp = ord(char)
        if 0x4E00 <= cp <= 0x9FFF:
            return "hanzi"
        elif 0x3000 <= cp <= 0x303F:
            return "punct"
        elif 0x0030 <= cp <= 0x0039:
            return "num"
        else:
            return "other"

    def extract_rhythmic_features(self, upper: str, lower: str) -> Dict[str, float]:
        """提取韵律特征"""
        from porm.engines.pingze import get_sequence
        u_tones = get_sequence(upper)
        l_tones = get_sequence(lower)

        if len(u_tones) == len(l_tones) and len(u_tones) > 0:
            opposite = sum(1 for u, lt in zip(u_tones, l_tones) if u * lt == -1)
            tonal_score = opposite / len(u_tones)
        else:
            tonal_score = 0.0

        return {
            "tonal_pattern_score": tonal_score,
            "rhythm_harmony": tonal_score * 0.8 + 0.2
        }

    def extract_statistical_features(self, upper: str, lower: str) -> Dict[str, float]:
        """提取统计特征"""
        upper_set = set(upper)
        lower_set = set(lower)

        if len(upper_set) > 0 and len(lower_set) > 0:
            overlap = len(upper_set & lower_set)
            union = len(upper_set | lower_set)
            overlap_ratio = overlap / union if union > 0 else 0.0
        else:
            overlap_ratio = 0.0

        length_balance = 1.0 if len(upper) == len(lower) else 0.0

        return {
            "char_overlap_ratio": overlap_ratio,
            "length_balance": length_balance
        }

    def extract_all_features(self, upper: str, lower: str) -> NLPFeatures:
        """提取全部特征"""
        syntactic = self.extract_syntactic_features(upper, lower)
        rhythmic = self.extract_rhythmic_features(upper, lower)
        statistical = self.extract_statistical_features(upper, lower)

        return NLPFeatures(
            pos_match_rate=syntactic["pos_match_rate"],
            structure_parallelism=syntactic["structure_parallelism"],
            syntactic_congruence=syntactic["syntactic_congruence"],
            tonal_pattern_score=rhythmic["tonal_pattern_score"],
            rhythm_harmony=rhythmic["rhythm_harmony"],
            char_overlap_ratio=statistical["char_overlap_ratio"],
            length_balance=statistical["length_balance"]
        )


class WeightedAverageFusion:
    """加权平均融合"""

    FEATURE_WEIGHTS = np.array([
        0.30,  # pos_match_rate
        0.25,  # structure_parallelism
        0.10,  # syntactic_congruence
        0.15,  # tonal_pattern_score
        0.10,  # rhythm_harmony
        0.05,  # char_overlap_ratio
        0.05,  # length_balance
    ])

    def __init__(self, nlp_weight: float = 0.4, llm_weight: float = 0.6):
        self.nlp_weight = nlp_weight
        self.llm_weight = llm_weight

    def fuse(self, nlp_features: NLPFeatures, llm_output: LLMOutput) -> FusionResult:
        nlp_vector = np.clip(nlp_features.to_vector(), 0.0, 1.0)
        nlp_score = float(np.dot(nlp_vector, self.FEATURE_WEIGHTS)) * 100
        llm_score = llm_output.raw_score

        final_score = self.nlp_weight * nlp_score + self.llm_weight * llm_score
        agreement = 1.0 - min(abs(nlp_score - llm_score) / 100.0, 1.0)
        confidence = 0.5 + 0.5 * agreement

        return FusionResult(
            final_score=round(final_score, 2),
            nlp_contribution=round(nlp_score, 2),
            llm_contribution=round(llm_score, 2),
            fusion_confidence=round(confidence, 2),
            decision_basis=[
                f"NLP 加权得分：{nlp_score:.2f}",
                f"LLM 原始得分：{llm_score:.2f}",
                f"一致性：{agreement:.2%}"
            ],
            feature_importance={
                "pos_match": 0.30, "structure": 0.25, "syntax": 0.10,
                "tonal": 0.15, "rhythm": 0.10, "overlap": 0.05, "balance": 0.05
            }
        )


class BayesianFusion:
    """高斯贝叶斯融合"""

    def __init__(self, nlp_sigma: float = 15.0, llm_sigma: float = 12.0, prior_sigma: float = 25.0):
        self.nlp_sigma = nlp_sigma
        self.llm_sigma = llm_sigma
        self.prior_sigma = prior_sigma

    def fuse(self, nlp_features: NLPFeatures, llm_output: LLMOutput) -> FusionResult:
        nlp_vector = np.clip(nlp_features.to_vector(), 0.0, 1.0)
        nlp_score = float(np.dot(nlp_vector, WeightedAverageFusion.FEATURE_WEIGHTS)) * 100
        llm_score = llm_output.raw_score

        tau_nlp = 1.0 / (self.nlp_sigma ** 2)
        tau_llm = 1.0 / (self.llm_sigma ** 2)
        tau_prior = 1.0 / (self.prior_sigma ** 2)

        tau_post = tau_nlp + tau_llm + tau_prior
        mu_post = (tau_nlp * nlp_score + tau_llm * llm_score + tau_prior * 50.0) / tau_post
        sigma_post = np.sqrt(1.0 / tau_post)
        confidence = 1.0 - min(sigma_post / self.prior_sigma, 1.0)

        return FusionResult(
            final_score=round(mu_post, 2),
            nlp_contribution=round(nlp_score, 2),
            llm_contribution=round(llm_score, 2),
            fusion_confidence=round(confidence, 2),
            decision_basis=[
                f"NLP 观测：{nlp_score:.2f} (σ={self.nlp_sigma})",
                f"LLM 观测：{llm_score:.2f} (σ={self.llm_sigma})",
                f"后验均值：{mu_post:.2f} (σ={sigma_post:.2f})"
            ]
        )


class FusionEngine:
    """融合引擎"""

    def __init__(self, strategy: FusionStrategy = FusionStrategy.WEIGHTED_AVERAGE):
        self.feature_extractor = FeatureExtractor()
        self.strategy = strategy

        if strategy == FusionStrategy.WEIGHTED_AVERAGE:
            self.fusion_algorithm = WeightedAverageFusion()
        else:
            self.fusion_algorithm = BayesianFusion()

    def fuse(
        self,
        upper: str,
        lower: str,
        llm_raw_output: str,
        llm_parsed_result: Dict[str, Any]
    ) -> FusionResult:
        nlp_features = self.feature_extractor.extract_all_features(upper, lower)
        llm_output = LLMOutput(
            raw_score=llm_parsed_result.get('score', 0),
            confidence=llm_parsed_result.get('confidence', 0.8),
            reasoning=llm_parsed_result.get('reason', '')
        )
        return self.fusion_algorithm.fuse(nlp_features, llm_output)

    def get_feature_analysis(self, upper: str, lower: str) -> Dict[str, Any]:
        features = self.feature_extractor.extract_all_features(upper, lower)
        return {
            "syntactic": {
                "pos_match": features.pos_match_rate,
                "structure": features.structure_parallelism
            },
            "rhythmic": {
                "tonal": features.tonal_pattern_score,
                "rhythm": features.rhythm_harmony
            },
            "statistical": {
                "overlap": features.char_overlap_ratio,
                "balance": features.length_balance
            }
        }