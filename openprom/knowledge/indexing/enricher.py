"""Poem enrichment: auto-compute form, couplets, meter, rhyme category.

This is the "value-add" step that turns raw chinese-poetry data into
retrieval-ready knowledge with structured metadata.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_FORM_RULES = [
    (4, 5, "wu jue"),
    (4, 7, "qi jue"),
    (8, 5, "wu lv"),
    (8, 7, "qi lv"),
    (4, 4, "si yan"),
]


def detect_form(content: str) -> str:
    """Detect poetic form from line count and chars-per-line."""
    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    if not lines:
        return ""
    n_lines = len(lines)
    clean_lines = []
    for line in lines:
        clean = re.sub(r"[，。！？；：、\s]", "", line)
        clean_lines.append(clean)
    if not clean_lines:
        return ""
    lengths = sorted(len(ln) for ln in clean_lines if ln)
    if not lengths:
        return ""
    median_len = lengths[len(lengths) // 2]

    for rule_lines, rule_chars, form in _FORM_RULES:
        if n_lines == rule_lines and median_len == rule_chars:
            return form
    if n_lines >= 2 and len(set(lengths)) > 1:
        return "ci"
    if n_lines == 2:
        return "duilian"
    return "guti"


def split_couplet(content: str) -> List[Dict[str, str]]:
    """Split a poem into couplet pairs with position labels."""
    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    couplets = []
    positions = ["shoulian", "hanlian", "jinglian", "weilian"]
    for i in range(0, len(lines) - 1, 2):
        pos_idx = i // 2
        position = positions[pos_idx] if pos_idx < len(positions) else f"couplet_{pos_idx + 1}"
        couplets.append(
            {
                "upper": lines[i],
                "lower": lines[i + 1] if i + 1 < len(lines) else "",
                "position": position,
            }
        )
    return couplets


def detect_rhyme_category(content: str) -> Optional[str]:
    """Detect rhyme category from last character via RhymeBook."""
    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    if not lines:
        return None
    last_char = lines[-1][-1] if lines[-1] else ""
    if not last_char:
        return None
    try:
        from openprom.data.loader import RhymeBook

        rhymebook = RhymeBook.get()
        return rhymebook.get_rhyme_category(last_char)
    except Exception as e:
        logger.debug(f"Rhyme detection failed: {e}")
        return None


def enrich_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich a normalized record with form, couplets, and rhyme info."""
    content = record.get("content", "")
    if not record.get("form"):
        record["form"] = detect_form(content)
    record["couplets"] = split_couplet(content)
    rhyme_cat = detect_rhyme_category(content)
    if rhyme_cat:
        record["rhyme_category"] = rhyme_cat
    return record


def enrich_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich a batch of normalized records."""
    enriched = []
    for rec in records:
        try:
            enriched.append(enrich_record(rec))
        except Exception as e:
            logger.warning(f"Failed to enrich record {rec.get('id', '?')}: {e}")
            enriched.append(rec)
    return enriched
