"""Rule signal extraction for retrieval ranking.

Extracts deterministic features from L5 rule engines (meter, pingze, rhyme)
that participate in the retrieval ranking pipeline (Rerank fusion).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def compute_meter_match(candidate_text: str, target_form: Optional[str] = None) -> float:
    """Compute how well a candidate's meter matches a target form. Returns 0..1."""
    if not target_form:
        return 0.5
    try:
        from openprom.engines.meter import get_engine

        engine = get_engine()
        lines = [ln.strip() for ln in candidate_text.split("\n") if ln.strip()]
        if not lines:
            return 0.0
        if target_form in ("wu jue", "qi jue", "wu lv", "qi lv"):
            result = engine.find_best_shi(lines, top_k=1)
            if result and len(result) > 0:
                best = result[0] if isinstance(result, list) else result
                match_rate = getattr(best, "match_rate", None)
                if match_rate is not None:
                    return float(match_rate)
                pattern_name = getattr(best, "pattern_name", "")
                if target_form in pattern_name:
                    return 0.9
        return 0.3
    except Exception as e:
        logger.debug(f"meter_match computation failed: {e}")
        return 0.5


def compute_rhyme_consistency(
    candidate_text: str,
    target_rhyme_category: Optional[str] = None,
) -> float:
    """Check if candidate's rhyme endings match target category. Returns 0..1."""
    if not target_rhyme_category:
        return 0.5
    try:
        from openprom.data.loader import RhymeBook

        rhymebook = RhymeBook.get()
        lines = [ln.strip() for ln in candidate_text.split("\n") if ln.strip()]
        if not lines:
            return 0.0
        last_char = lines[-1][-1] if lines[-1] else ""
        if not last_char:
            return 0.0
        char_rhyme = rhymebook.get_rhyme_category(last_char)
        if char_rhyme and char_rhyme == target_rhyme_category:
            return 1.0
        return 0.2
    except Exception as e:
        logger.debug(f"rhyme_consistency computation failed: {e}")
        return 0.5


def compute_form_match(
    candidate_metadata: Dict[str, Any], target_form: Optional[str] = None
) -> float:
    """Check if candidate's form matches target. Returns 0.0 or 1.0."""
    if not target_form:
        return 0.5
    candidate_form = candidate_metadata.get("form", "")
    return 1.0 if candidate_form == target_form else 0.0


def extract_rule_signals(
    candidate_text: str,
    candidate_metadata: Dict[str, Any],
    target_form: Optional[str] = None,
    target_rhyme_category: Optional[str] = None,
) -> Dict[str, float]:
    """Extract all rule signals for a candidate poem."""
    return {
        "meter_match": compute_meter_match(candidate_text, target_form),
        "rhyme_consistency": compute_rhyme_consistency(candidate_text, target_rhyme_category),
        "form_match": compute_form_match(candidate_metadata, target_form),
    }


def fuse_with_rule_signals(
    semantic_score: float,
    rule_signals: Dict[str, float],
    w_semantic: float = 0.6,
    w_rule: float = 0.4,
) -> float:
    """Fuse semantic score with rule signals into final ranking score."""
    rule_values = [
        rule_signals.get("meter_match", 0.5),
        rule_signals.get("rhyme_consistency", 0.5),
        rule_signals.get("form_match", 0.5),
    ]
    rule_combined = sum(rule_values) / len(rule_values)
    return w_semantic * semantic_score + w_rule * rule_combined
