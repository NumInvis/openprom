"""Couplet scoring service.

Replaces the previous DualAPITechniqueScorer. It relies entirely on the
configured LLM plus rule-based formal analysis; no local models are loaded.

Every ``analyze`` call is instrumented with a ``TaskTrace`` that records
formal analysis, both LLM calls, Saddle QC, and the final score, so scoring
flows are observable in the same trace store as generation flows.
"""

import logging
import time
import uuid
from typing import Any, Dict, List
from dataclasses import dataclass, field

from openprom.infrastructure.config import get_prompt_service, get_settings
from openprom.core.saddle_engineering import SaddleEngineering
from openprom.core.base_analyzer import analyze_formal, generate_overall_comment
from openprom.services.llm_client import get_llm_client
from openprom.utils import normalize_score, calculate_weighted_score

logger = logging.getLogger(__name__)


@dataclass
class CoupletScore:
    """Complete couplet scoring result."""
    upper: str
    lower: str
    formal_score: float = 0.0
    technique_score: float = 0.0
    first_impression_score: float = 0.0
    first_impression_reason: str = ""
    special_attention: Dict[str, Any] = field(default_factory=dict)
    llm_technique_score: float = 0.0
    llm_technique_evaluation: Dict[str, Any] = field(default_factory=dict)
    llm_rhetoric_score: float = 0.0
    llm_rhetoric_evaluation: Dict[str, Any] = field(default_factory=dict)
    final_technique_score: float = 0.0
    artistic_score: float = 0.0
    impression_score: float = 0.0
    total_score: float = 0.0
    grade: str = ""
    pingze_score: float = 0.0
    warnings: List[str] = field(default_factory=list)
    comments: Dict[str, str] = field(default_factory=dict)
    word_analysis: List[Dict[str, Any]] = field(default_factory=list)
    saddle_applied: bool = False
    nlp_correction_applied: bool = False


class CoupletScorer:
    """Couplet scorer using LLM + rule-based formal analysis."""

    def __init__(self):
        self._client = get_llm_client()
        self._prompt_service = get_prompt_service()
        self._saddle = SaddleEngineering()
        self._settings = get_settings()
        self._technique_weights = dict(self._settings.scoring.technique_weights)
        self._total_weights = dict(self._settings.scoring.total_weights)

    def _first_call(self, upper: str, lower: str) -> Dict[str, Any]:
        prompt_template = self._prompt_service.get_prompt("first_api_call")
        prompt = prompt_template.render(upper=upper, lower=lower)
        try:
            return self._client.chat(
                prompt=prompt,
                temperature=self._settings.api.temperature_impression,
                json_mode=True,
            )
        except Exception as e:
            logger.error(f"First impression LLM call failed: {e}")
            return {
                "first_impression_score": 30,
                "first_impression_reason": "LLM 调用失败，使用默认印象分",
                "special_attention": {},
                "fallback": True,
            }

    def _second_call(self, upper: str, lower: str, special_attention: Dict[str, Any]) -> Dict[str, Any]:
        import json
        prompt_template = self._prompt_service.get_prompt("second_api_call")
        key_insights = json.dumps(special_attention, ensure_ascii=False)[:300]
        prompt = prompt_template.render(upper=upper, lower=lower, key_insights=key_insights)
        try:
            return self._client.chat(
                prompt=prompt,
                temperature=self._settings.api.temperature_technique,
                json_mode=True,
            )
        except Exception as e:
            logger.error(f"Second analysis LLM call failed: {e}")
            return {
                "technique_score": 30,
                "technique_evaluation": {},
                "rhetoric_score": 30,
                "rhetoric_evaluation": {},
                "word_analysis": [],
                "fallback": True,
            }

    def analyze(self, upper: str, lower: str) -> CoupletScore:
        """Run the full scoring pipeline.

        A ``TaskTrace`` is created and persisted so every scoring call is
        observable in the trace store alongside generation traces.
        """
        from openprom.agents import TaskTrace

        trace = TaskTrace(
            task_name="analyze_couplet",
            task_id=f"s-{uuid.uuid4().hex[:12]}",
            started_at=time.time(),
        )

        result = CoupletScore(upper=upper, lower=lower)

        formal_score, pingze_score, warnings = analyze_formal(upper, lower)
        result.formal_score = formal_score
        result.pingze_score = pingze_score
        result.warnings = warnings
        trace.add_step("formal_analysis", {
            "formal_score": formal_score,
            "pingze_score": pingze_score,
            "warnings_count": len(warnings),
        })

        if len(upper) != len(lower):
            result.grade = "不合格"
            result.total_score = 0.0
            result.comments = {"overall_comment": "上下联字数不等，无法评分。"}
            trace.success = False
            trace.error = "length_mismatch"
            trace.finished_at = time.time()
            self._persist_trace(trace)
            return result

        first = self._first_call(upper, lower)
        result.first_impression_score = normalize_score(first.get("first_impression_score", 0), max_score=100)
        result.first_impression_reason = first.get("first_impression_reason", "")
        result.special_attention = first.get("special_attention", {})
        trace.add_step("llm_call", {
            "round": 1,
            "label": "first_impression",
            "fallback": first.get("fallback", False),
            "score": result.first_impression_score,
        })

        second = self._second_call(upper, lower, result.special_attention)
        result.llm_technique_score = normalize_score(second.get("technique_score", 0), max_score=100)
        result.llm_technique_evaluation = second.get("technique_evaluation", {})
        result.llm_rhetoric_score = normalize_score(second.get("rhetoric_score", 0), max_score=100)
        result.llm_rhetoric_evaluation = second.get("rhetoric_evaluation", {})
        result.word_analysis = second.get("word_analysis", [])
        trace.add_step("llm_call", {
            "round": 2,
            "label": "technique_rhetoric",
            "fallback": second.get("fallback", False),
            "technique_score": result.llm_technique_score,
            "rhetoric_score": result.llm_rhetoric_score,
        })

        # Saddle engineering quality control
        nlp_features = {
            "pos_match_rate": self._compute_nlp_features(upper, lower),
            "pingze_score": pingze_score,
        }
        meter_analysis = {"is_valid": len(warnings) == 0, "warnings": warnings}
        saddle_t0 = time.time()
        saddle_ctx = self._saddle.execute(
            upper=upper,
            lower=lower,
            nlp_features=nlp_features,
            llm_raw_output=str(second),
            llm_parsed_result=second,
            meter_analysis=meter_analysis,
        )
        trace.add_step("saddle_check", {
            "applied": saddle_ctx.final_score != result.llm_technique_score * 100,
            "violations": len(saddle_ctx.validation_results),
        }, duration_ms=(time.time() - saddle_t0) * 1000)

        corrected_llm_score = saddle_ctx.llm_parsed_result.get("score", result.llm_technique_score)
        result.saddle_applied = saddle_ctx.final_score != result.llm_technique_score * 100
        result.nlp_correction_applied = saddle_ctx.llm_parsed_result.get("_nlp_correction_applied", False)

        technique_score = corrected_llm_score if result.saddle_applied else result.llm_technique_score
        scores = [technique_score, result.llm_rhetoric_score]
        weights = [
            self._technique_weights.get("llm_technique", 0.50),
            self._technique_weights.get("llm_rhetoric", 0.50),
        ]
        result.final_technique_score = calculate_weighted_score(scores, weights)
        result.technique_score = result.final_technique_score
        result.artistic_score = result.llm_rhetoric_score
        result.impression_score = result.first_impression_score

        total = (
            self._total_weights["formal"] * result.formal_score +
            self._total_weights["technique"] * result.technique_score +
            self._total_weights["artistic"] * result.artistic_score +
            self._total_weights["impression"] * result.impression_score
        )
        result.total_score = round(total * 100, 1)
        result.total_score = max(0.0, min(100.0, result.total_score))
        result.grade = self._determine_grade(result.total_score)

        result.comments = {
            "technique_comment": result.llm_technique_evaluation.get("overall_technique_comment", ""),
            "artistic_comment": result.llm_rhetoric_evaluation.get("overall_rhetoric_comment", ""),
            "impression_comment": result.first_impression_reason,
            "overall_comment": generate_overall_comment(
                result.formal_score, result.technique_score, result.artistic_score
            ),
        }

        trace.add_step("result", {
            "total_score": result.total_score,
            "grade": result.grade,
            "saddle_applied": result.saddle_applied,
        })
        trace.success = True
        trace.finished_at = time.time()
        self._persist_trace(trace)

        logger.info(f"Couplet scored | total={result.total_score} | grade={result.grade} | saddle={result.saddle_applied}")

        # Wire feedback ingestion: high-scoring couplets → knowledge base
        self._try_feedback_ingest(upper, lower, result.total_score)

        return result

    @staticmethod
    def _persist_trace(trace) -> None:
        """Best-effort trace persistence."""
        try:
            from openprom.infrastructure.task_trace import get_task_trace_store
            get_task_trace_store().save(trace)
        except Exception as e:
            logger.debug(f"Trace persistence skipped: {e}")

    def _try_feedback_ingest(self, upper: str, lower: str, score: float) -> None:
        """Non-blocking attempt to ingest high-scoring couplet into knowledge base."""
        try:
            from openprom.infrastructure.config.settings import get_settings
            settings = get_settings()
            features = getattr(settings, "features", None)
            knowledge = getattr(settings, "knowledge", None)
            if not (features and getattr(features, "knowledge_layer_v2", False)):
                return
            if not (knowledge and getattr(knowledge, "enabled", False)):
                return
            from openprom.knowledge.memory.feedback import get_feedback_ingestor
            ingestor = get_feedback_ingestor()
            content = f"{upper}\n{lower}"
            ingestor.ingest(content=content, score=score, meter_type="couplet")
        except Exception as e:
            logger.debug(f"Feedback ingest skipped: {e}")

    @staticmethod
    def _determine_grade(total_score: float) -> str:
        for threshold, grade in [(90, "优秀"), (75, "良好"), (60, "及格"), (0, "不合格")]:
            if total_score >= threshold:
                return grade
        return "不合格"

    @staticmethod
    def _compute_nlp_features(upper: str, lower: str) -> float:
        from openprom.engines.pingze import get_sequence
        try:
            u_tones = get_sequence(upper)
            l_tones = get_sequence(lower)
            if len(u_tones) == len(l_tones) and len(u_tones) > 0:
                opposite = sum(1 for u, lt in zip(u_tones, l_tones) if u * lt == -1)
                return opposite / len(u_tones)
        except Exception:
            pass
        return 0.0


def score_couplet(upper: str, lower: str) -> CoupletScore:
    """Convenience function."""
    return CoupletScorer().analyze(upper, lower)
