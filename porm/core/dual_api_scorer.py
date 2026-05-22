"""双 API 技法评分系统

版本：4.0.0
模型：Qwen3.5-9B-Instruct

功能：
    - 第一次 API 调用：第一印象评估
    - 第二次 API 调用：深度技法分析
    - Qwen 语义相似度计算
    - 加权评分
"""

import json
import logging
import time
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import threading

from porm.infrastructure.config import get_prompt_service, get_settings
from porm.core.fusion_engine import FusionEngine
from porm.core.saddle_engineering import SaddleEngineering
from porm.core.base_analyzer import analyze_formal, generate_overall_comment
from porm.utils import parse_llm_json_response, normalize_score, calculate_weighted_score

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DualAPIScore:
    """评分结果"""
    upper: str
    lower: str
    formal_score: float = 0.0
    technique_score: float = 0.0
    first_impression_score: float = 0.0
    first_impression_reason: str = ""
    special_attention: Dict[str, Any] = field(default_factory=dict)
    qwen_cosine_similarity: float = 0.0
    qwen_analysis: Dict[str, Any] = field(default_factory=dict)
    llm_technique_score: float = 0.0
    llm_technique_evaluation: Dict[str, Any] = field(default_factory=dict)
    llm_rhetoric_score: float = 0.0
    llm_rhetoric_evaluation: Dict[str, Any] = field(default_factory=dict)
    final_technique_score: float = 0.0
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    artistic_score: float = 0.0
    impression_score: float = 0.0
    total_score: float = 0.0
    grade: str = ""
    pingze_score: float = 0.0
    warnings: List[str] = field(default_factory=list)
    comments: Dict[str, str] = field(default_factory=dict)
    computation_log: List[str] = field(default_factory=list)


class DualAPITechniqueScorer:
    """双 API 评分器"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = None
        self._client_lock = threading.Lock()
        self._prompt_service = get_prompt_service()
        self._fusion_engine = FusionEngine(model_name="Qwen3.5-9B-Instruct")
        self._saddle = SaddleEngineering()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._healthy = True

        try:
            settings = get_settings()
            self.TECHNIQUE_WEIGHTS = dict(settings.scoring.technique_weights)
            self.TOTAL_WEIGHTS = dict(settings.scoring.total_weights)
            self.MAX_RETRIES = settings.api.max_retries
            self.RETRY_DELAY = settings.api.retry_delay
            self.TIMEOUT = settings.api.timeout
        except Exception:
            self.TECHNIQUE_WEIGHTS = {
                'qwen_cosine': 0.60,
                'llm_technique': 0.20,
                'llm_rhetoric': 0.20
            }
            self.TOTAL_WEIGHTS = {
                'formal': 0.30,
                'technique': 0.30,
                'artistic': 0.30,
                'impression': 0.10
            }
            self.MAX_RETRIES = 3
            self.RETRY_DELAY = 2.0
            self.TIMEOUT = 180.0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False

    def shutdown(self):
        if self._executor:
            self._executor.shutdown(wait=True)

    def _get_client(self):
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is not None:
                return self._client
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            return self._client

    def _call_llm(self, prompt_name: str, **vars) -> Tuple[Dict[str, Any], bool]:
        prompt_template = self._prompt_service.get_prompt(prompt_name)
        prompt = prompt_template.render(**vars)

        for attempt in range(self.MAX_RETRIES):
            try:
                client = self._get_client()
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    timeout=self.TIMEOUT
                )

                content = response.choices[0].message.content
                result = parse_llm_json_response(content)
                return result, True

            except Exception as e:
                logger.warning(f"API 调用失败 (尝试{attempt+1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)

        # Return a conservative fallback with error marker
        return {"error": "API 调用失败", "score": 30, "confidence": 0.0, "fallback": True}, False

    def _first_api_call(self, upper: str, lower: str) -> Dict[str, Any]:
        logger.info("第一次 API 调用：第一印象评估")
        result, success = self._call_llm("first_api_call", upper=upper, lower=lower)

        if success:
            logger.info("第一次 API 调用成功")
        else:
            logger.error("第一次 API 调用失败")

        return result

    def _compute_qwen_similarity(self, upper: str, lower: str) -> Dict[str, Any]:
        logger.info("Qwen 语义相似度计算")

        try:
            if len(upper) != len(lower):
                return {
                    "cosine_similarity": 0.0,
                    "normalized_similarity": 0.0,
                    "error": "字数不等"
                }

            extractor = self._fusion_engine.feature_extractor
            result = extractor.extract_semantic_features(upper, lower)

            return {
                "cosine_similarity": result.get("semantic_similarity", 0.0),
                "normalized_similarity": result.get("normalized_similarity", 0.0),
                "char_level_analysis": result.get("char_level_analysis", [])
            }

        except Exception as e:
            logger.error(f"Qwen 计算失败：{e}")
            return {
                "cosine_similarity": 0.0,
                "normalized_similarity": 0.0,
                "error": str(e)
            }

    def _second_api_call(
        self,
        upper: str,
        lower: str,
        special_attention: Dict[str, Any],
        qwen_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info("第二次 API 调用：深度分析")

        key_insights = json.dumps(special_attention, ensure_ascii=False)[:200]
        qwen_score = qwen_analysis.get("normalized_similarity", 0.0)

        result, success = self._call_llm(
            "second_api_call",
            upper=upper,
            lower=lower,
            key_insights=key_insights,
            qwen_score=f"{qwen_score:.4f}"
        )

        return result

    def analyze(self, upper: str, lower: str) -> DualAPIScore:
        """执行完整分析流程"""
        result = DualAPIScore(upper=upper, lower=lower)

        # 步骤 1: 形式分析
        formal_score, pingze_score, warnings = analyze_formal(upper, lower)
        result.formal_score = formal_score
        result.pingze_score = pingze_score
        result.warnings = warnings

        if len(upper) != len(lower):
            result.grade = "不合格"
            result.total_score = 0.0
            return result

        # 步骤 2: 并行执行
        future_first = self._executor.submit(self._first_api_call, upper, lower)
        future_qwen = self._executor.submit(self._compute_qwen_similarity, upper, lower)

        first_result = future_first.result(timeout=300)
        qwen_result = future_qwen.result(timeout=180)

        result.first_impression_score = normalize_score(
            first_result.get("first_impression_score", 0), max_score=100
        )
        result.first_impression_reason = first_result.get("first_impression_reason", "")
        result.special_attention = first_result.get("special_attention", {})

        result.qwen_cosine_similarity = qwen_result.get("cosine_similarity", 0.0)
        result.qwen_analysis = qwen_result

        # 步骤 3: 第二次 API 调用
        second_result = self._second_api_call(
            upper, lower, result.special_attention, qwen_result
        )

        result.llm_technique_score = normalize_score(
            second_result.get("technique_score", 0), max_score=100
        )
        result.llm_technique_evaluation = second_result.get("technique_evaluation", {})

        result.llm_rhetoric_score = normalize_score(
            second_result.get("rhetoric_score", 0), max_score=100
        )
        result.llm_rhetoric_evaluation = second_result.get("rhetoric_evaluation", {})

        # 步骤 4: 计算最终分数
        qwen_normalized = qwen_result.get("normalized_similarity", 0.0)

        scores = [
            qwen_normalized,
            result.llm_technique_score,
            result.llm_rhetoric_score
        ]
        weights = [
            self.TECHNIQUE_WEIGHTS.get('qwen_cosine', 0.60),
            self.TECHNIQUE_WEIGHTS.get('llm_technique', 0.20),
            self.TECHNIQUE_WEIGHTS.get('llm_rhetoric', 0.20)
        ]

        final_technique = calculate_weighted_score(scores, weights)
        result.final_technique_score = final_technique
        result.technique_score = final_technique

        result.artistic_score = result.llm_rhetoric_score
        result.impression_score = result.first_impression_score

        # 计算总分
        total = (
            self.TOTAL_WEIGHTS['formal'] * result.formal_score +
            self.TOTAL_WEIGHTS['technique'] * result.technique_score +
            self.TOTAL_WEIGHTS['artistic'] * result.artistic_score +
            self.TOTAL_WEIGHTS['impression'] * result.impression_score
        )
        result.total_score = round(total * 100, 1)

        # Clamp score to valid range
        result.total_score = max(0.0, min(100.0, result.total_score))

        # 评级
        for threshold, grade in [(90, "优秀"), (75, "良好"), (60, "及格"), (0, "不合格")]:
            if result.total_score >= threshold:
                result.grade = grade
                break

        # 评语
        result.comments = {
            "technique_comment": result.llm_technique_evaluation.get("overall_technique_comment", ""),
            "artistic_comment": result.llm_rhetoric_evaluation.get("overall_rhetoric_comment", ""),
            "impression_comment": result.first_impression_reason,
            "overall_comment": generate_overall_comment(
                result.formal_score, result.technique_score, result.artistic_score
            )
        }

        logger.info(f"分析完成 | 总分：{result.total_score} | 等级：{result.grade}")
        return result


def analyze_dual_api(
    upper: str,
    lower: str,
    api_key: str,
    base_url: str,
    model: str
) -> DualAPIScore:
    """便捷函数"""
    with DualAPITechniqueScorer(api_key, base_url, model) as scorer:
        return scorer.analyze(upper, lower)
