"""Meter detection exposed as an LLM-callable Tool.

This module wraps the existing rule-based engines (`pingze`, `meter`) into a
shape that the generation agents can call via function-calling. It also produces
rhyme-word hints when the meter gradient cannot descend by model reasoning alone.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from openprom.data.loader import RhymeBook
from openprom.engines.meter import get_engine as get_meter_engine
from openprom.engines.pingze import get_sequence
from openprom.infrastructure.config.settings import get_settings

logger = logging.getLogger(__name__)

# 常用字加权：出现频率更高的字优先推荐给 LLM
_COMMON_CHAR_RANK: Dict[str, int] = {
    # 平声常用韵字（部分示例，可按需扩展）
    "一": 1,
    "天": 1,
    "烟": 2,
    "然": 2,
    "山": 1,
    "边": 2,
    "间": 1,
    "年": 1,
    "前": 1,
    "春": 1,
    "风": 1,
    "中": 1,
    "空": 1,
    "红": 1,
    "东": 2,
    "同": 3,
    "江": 1,
    "长": 1,
    "芳": 2,
    "阳": 1,
    "乡": 2,
    "堂": 2,
    "香": 1,
    "光": 1,
    "霜": 2,
    "窗": 2,
    "凉": 2,
    "声": 1,
    "城": 2,
    "明": 2,
    "情": 2,
    "行": 2,
}


def _normalize_text(text: str) -> str:
    """Normalize punctuation and whitespace."""
    # Keep newlines to separate lines; strip common punctuation.
    import re

    text = re.sub(r"[，。、；：！？\"“”‘’()（）【】]", "", text)
    return text.strip()


def _split_lines(text: str) -> List[str]:
    """Split text into lines for shi/ci; for couplet use first two lines."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return lines


def _detect_couplet_violations(
    upper: str, lower: str
) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """Check couplet formal rules.

    Returns (is_compliant, violation_messages, tone_details).
    """
    violations: List[str] = []
    details: List[Dict[str, Any]] = []

    if len(upper) != len(lower):
        violations.append(f"字数不等：上联{len(upper)}字，下联{len(lower)}字")
        return False, violations, details

    u_seq = get_sequence(upper)
    l_seq = get_sequence(lower)

    # 二四六分明
    key_pos = list(range(1, len(upper), 2))
    for i in key_pos:
        if u_seq[i] * l_seq[i] != -1:
            violations.append(
                f"第{i + 1}字未做到二四六分明：上联“{upper[i]}”({u_seq[i]}) 对 下联“{lower[i]}”({l_seq[i]})"
            )
            details.append(
                {
                    "pos": i,
                    "rule": "二四六分明",
                    "upper_char": upper[i],
                    "upper_tone": u_seq[i],
                    "lower_char": lower[i],
                    "lower_tone": l_seq[i],
                }
            )

    # 仄起平落
    if u_seq[-1] != -1:
        violations.append(f"上联尾字“{upper[-1]}”非仄声")
        details.append(
            {"pos": len(upper) - 1, "rule": "上联尾字仄声", "char": upper[-1], "tone": u_seq[-1]}
        )
    if l_seq[-1] != 1:
        violations.append(f"下联尾字“{lower[-1]}”非平声")
        details.append(
            {"pos": len(lower) - 1, "rule": "下联尾字平声", "char": lower[-1], "tone": l_seq[-1]}
        )

    # 三仄尾/三平尾
    for name, tones, text_line in [("上联", u_seq, upper), ("下联", l_seq, lower)]:
        if len(tones) >= 3:
            last3 = tones[-3:]
            definite = [t for t in last3 if t != 0]
            if len(definite) >= 2 and all(t < 0 for t in definite):
                violations.append(f"{name}三仄尾")
                details.append(
                    {"rule": "三仄尾", "line": name, "chars": text_line[-3:], "tones": last3}
                )
            if len(definite) >= 2 and all(t > 0 for t in definite):
                violations.append(f"{name}三平尾")
                details.append(
                    {"rule": "三平尾", "line": name, "chars": text_line[-3:], "tones": last3}
                )

    return len(violations) == 0, violations, details


def check_meter(
    text: str, meter_type: str, pattern_name: Optional[str] = None, strict: bool = False
) -> Dict[str, Any]:
    """Main tool entrypoint: check meter for shi/ci/couplet.

    Returns a dict suitable for both HTTP API and LLM tool_result.
    When ``is_compliant`` is False, the ``fixes`` field contains actionable
    suggestions the LLM can use to precisely correct violations.
    """
    settings = get_settings()
    threshold = (
        settings.tools.meter_strict_match_rate_threshold
        if strict
        else settings.tools.meter_match_rate_threshold
    )

    text = _normalize_text(text)
    lines = _split_lines(text)
    result: Dict[str, Any] = {
        "text": text,
        "meter_type": meter_type,
        "pingze_sequence": [],
        "matched_meters": [],
        "violations": [],
        "rhyme_suggestions": [],
        "is_compliant": False,
        "tone_details": [],
        "fixes": [],
    }

    if meter_type == "couplet":
        upper = lines[0] if len(lines) > 0 else ""
        lower = lines[1] if len(lines) > 1 else ""
        is_compliant, violations, details = _detect_couplet_violations(upper, lower)
        result["pingze_sequence"] = (
            [get_sequence(upper), get_sequence(lower)] if upper and lower else []
        )
        result["is_compliant"] = is_compliant
        result["violations"] = violations
        result["tone_details"] = details
        if not is_compliant:
            result["fixes"] = _build_couplet_fixes(upper, lower, details)
            if any("下联尾字" in v for v in violations):
                result["rhyme_suggestions"] = get_rhyme_candidates(
                    lower[-1], tone="ping", count=settings.tools.rhyme_max_suggestions
                )
        return result

    # shi or ci
    if not lines:
        result["violations"].append("文本为空或无法分行")
        return result

    engine = get_meter_engine(threshold=threshold)
    if pattern_name:
        if meter_type == "shi":
            match = engine.match_shi(lines, pattern_name)
        else:
            match = engine.match_ci(lines, pattern_name)
        matches = [match]
    else:
        if meter_type == "shi":
            matches = engine.find_best_shi(lines, top_k=5)
        else:
            matches = engine.find_best_ci(lines, top_k=5)

    result["matched_meters"] = [m.to_dict() for m in matches]
    best = matches[0] if matches else None

    if best:
        result["is_compliant"] = best.is_valid
        result["violations"] = [
            f"{err.get('line', 0) + 1}行第{err.get('pos', 0) + 1}字\u201c{err.get('char')}\u201d当{err.get('expected')}而{err.get('actual')}"
            for err in best.errors
        ]
        result["pingze_sequence"] = [get_sequence(line) for line in lines]

        if not best.is_valid:
            result["fixes"] = _build_shi_fixes(best.errors, lines, settings)
            last_line = lines[-1]
            last_char = last_line[-1] if last_line else ""
            for err in best.errors:
                if (
                    err.get("line") == len(lines) - 1
                    and err.get("pos") == len(last_line) - 1
                    and err.get("expected") == "\u5e73"
                ):
                    result["rhyme_suggestions"] = get_rhyme_candidates(
                        last_char, tone="ping", count=settings.tools.rhyme_max_suggestions
                    )
                    break
    else:
        result["violations"].append("未找到可匹配的格律模板")

    return result


def _build_couplet_fixes(upper: str, lower: str, details: List[Dict]) -> List[Dict[str, Any]]:
    """Build actionable fix suggestions for couplet violations."""
    fixes = []
    tone_map = {1: "\u5e73", -1: "\u4e36", 0: "\u53ef\u5e73\u53ef\u4e36"}
    for d in details:
        pos = d.get("pos", 0)
        rule = d.get("rule", "")
        fix: Dict[str, Any] = {"line": 0, "position": pos + 1}

        if "\u4e8c\u56db\u516d\u5206\u660e" in rule:
            fix["line"] = "\u4e0a\u8054+\u4e0b\u8054"
            fix["current_chars"] = f"{d.get('upper_char', '')}/{d.get('lower_char', '')}"
            fix["current_tones"] = (
                f"{tone_map.get(d.get('upper_tone', 0), '?')}/{tone_map.get(d.get('lower_tone', 0), '?')}"
            )
            fix["needed"] = "\u4e0a\u4e0b\u8054\u8be5\u4f4d\u7f6e\u5e73\u4e36\u76f8\u53cd"
            fix["description"] = (
                f"\u7b2c{pos + 1}\u5b57\u4e0a\u4e0b\u8054\u5e73\u4e36\u5e94\u76f8\u53cd\uff1a"
                f"\u4e0a\u8054\u201c{d.get('upper_char', '')}\u201d({tone_map.get(d.get('upper_tone', 0), '?')}) "
                f"\u5bf9 \u4e0b\u8054\u201c{d.get('lower_char', '')}\u201d({tone_map.get(d.get('lower_tone', 0), '?')})"
            )
        elif "\u4e0a\u8054\u5c3e\u5b57" in rule:
            fix["line"] = "\u4e0a\u8054"
            fix["current_char"] = d.get("char", "")
            fix["current_tone"] = tone_map.get(d.get("tone", 0), "?")
            fix["needed"] = "\u4e36\u58f0"
            fix["description"] = (
                f"\u4e0a\u8054\u5c3e\u5b57\u201c{d.get('char', '')}\u201d\u5e94\u4e3a\u4e36\u58f0"
            )
            fix["rhyme_candidates"] = get_rhyme_candidates(d.get("char", ""), tone="ze", count=8)
        elif "\u4e0b\u8054\u5c3e\u5b57" in rule:
            fix["line"] = "\u4e0b\u8054"
            fix["current_char"] = d.get("char", "")
            fix["current_tone"] = tone_map.get(d.get("tone", 0), "?")
            fix["needed"] = "\u5e73\u58f0"
            fix["description"] = (
                f"\u4e0b\u8054\u5c3e\u5b57\u201c{d.get('char', '')}\u201d\u5e94\u4e3a\u5e73\u58f0"
            )
            fix["rhyme_candidates"] = get_rhyme_candidates(d.get("char", ""), tone="ping", count=8)
        else:
            fix["description"] = str(rule)

        fixes.append(fix)
    return fixes


def _build_shi_fixes(errors: List[Dict], lines: List[str], settings) -> List[Dict[str, Any]]:
    """Build actionable fix suggestions for shi/ci violations."""
    fixes = []
    for err in errors:
        line_idx = err.get("line", 0)
        pos = err.get("pos", 0)
        char = err.get("char", "")
        expected = err.get("expected", "")
        actual = err.get("actual", "")

        line_text = lines[line_idx] if line_idx < len(lines) else ""
        fix: Dict[str, Any] = {
            "line": line_idx + 1,
            "position": pos + 1,
            "current_char": char,
            "current_tone": actual,
            "needed_tone": expected,
            "description": (
                f"\u7b2c{line_idx + 1}\u53e5\u7b2c{pos + 1}\u5b57\u201c{char}\u201d\u662f"
                f"{actual}\u58f0\uff0c\u5e94\u6539\u4e3a{expected}\u58f0"
            ),
        }

        if pos == len(line_text) - 1:
            tone = "ping" if expected == "\u5e73" else "ze"
            fix["rhyme_candidates"] = get_rhyme_candidates(
                char, tone=tone, count=settings.tools.rhyme_max_suggestions
            )

        fixes.append(fix)
    return fixes


def get_rhyme_candidates(char: str, tone: Optional[str] = None, count: int = 8) -> List[str]:
    """Return candidate characters sharing the same rhyme category and tone.

    Args:
        char: reference character (single Chinese char)
        tone: "ping" or "ze"; if None, infer from char.
        count: max number of candidates.
    """
    settings = get_settings()
    book_name = settings.tools.rhyme_book
    rhyme = RhymeBook.get()
    book_data = rhyme._data.get(book_name) if rhyme._data else None
    if not book_data or len(book_data) < 2:
        return []

    # Infer desired tone
    if tone is None:
        inferred = rhyme.get_tone(char, book_name)
        tone = "ping" if inferred == 1 else "ze" if inferred == -1 else "ping"

    target_tone_val = 1 if tone == "ping" else -1
    categories = book_data[0] if target_tone_val == 1 else book_data[1]

    target_category: Optional[List[str]] = None
    for cat in categories:
        if char in cat:
            target_category = cat
            break

    if target_category is None:
        # Fallback: return first `count` chars from the first matching-tone category
        target_category = categories[0] if categories else []

    candidates = [c for c in target_category if c != char]

    # Sort by commonness (heuristic rank)
    candidates.sort(key=lambda c: (_COMMON_CHAR_RANK.get(c, 99), c))

    return candidates[:count]


def explain_rule(rule: str) -> str:
    """Return a concise rule explanation for LLM self-correction."""
    explanations = {
        "pingze": (
            "平仄：中古汉语四声中，平声（约对应今拼音1、2声）为平，"
            "上、去、入声为仄。对联要求二四六位置平仄相对，上联尾字仄、下联尾字平。"
        ),
        "duizhang": (
            "对仗：上下联在相同位置词性、结构、语义要相互对应，如名词对名词、动词对动词。"
        ),
        "rhyme": ("押韵：律诗偶数句（二四六八句）及首句可入韵时须押同一韵部，多用平声韵。"),
        "sanpingwei": "三平尾：一句末尾连续三字皆平声，为格律大忌。",
        "sanzewei": "三仄尾：一句末尾连续三字皆仄声，为格律大忌。",
    }
    return explanations.get(rule, "暂无该规则说明。")
