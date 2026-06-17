"""Poem normalization: field mapping, text cleaning, standardization.

Converts raw chinese-poetry JSON into the unified schema.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize poem text: strip, clean punctuation, remove excess whitespace."""
    if not text:
        return ""
    text = text.strip()
    # Remove leading/trailing punctuation artifacts
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_record(item: Dict[str, Any], idx: int = 0) -> Optional[Dict[str, Any]]:
    """Normalize a raw poem record to the unified schema.

    Handles various field names from chinese-poetry JSON format.
    Returns None if the record is invalid.
    """
    # Extract ID
    poem_id = item.get("id") or item.get("rank") or f"poem_{idx}"

    # Extract title
    title = item.get("title") or item.get("rhythmic") or ""
    title = title.strip()

    # Extract author
    author = item.get("author") or item.get("诗人") or ""
    author = author.strip()

    # Extract dynasty
    dynasty = item.get("dynasty") or item.get("朝代") or ""
    dynasty = dynasty.strip()

    # Extract content: handle multiple formats
    content = ""
    paragraphs = item.get("paragraphs") or item.get("content") or item.get("text")
    if isinstance(paragraphs, list):
        content = "\n".join(p.strip() for p in paragraphs if p.strip())
    elif isinstance(paragraphs, str):
        content = paragraphs.strip()

    if not content:
        return None

    # Extract tags
    tags = item.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Extract theme
    theme = item.get("theme", "")

    return {
        "id": str(poem_id),
        "title": title,
        "author": author,
        "dynasty": dynasty,
        "content": content,
        "tags": tags,
        "theme": theme,
        "source": item.get("source", "chinese-poetry"),
        "confidence": float(item.get("confidence", 0.95)),
        "version": item.get("version", ""),
    }


def normalize_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize a batch of raw records, dropping invalid ones."""
    normalized = []
    for idx, item in enumerate(records):
        rec = normalize_record(item, idx)
        if rec:
            normalized.append(rec)
    dropped = len(records) - len(normalized)
    if dropped > 0:
        logger.warning(f"Dropped {dropped} invalid records out of {len(records)}")
    return normalized
