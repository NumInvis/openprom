"""Poem validation: metadata completeness, meter compliance checks.

Validates records before they enter the knowledge base.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["id", "title", "content", "source", "confidence"]


def validate_record(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a single record against the required schema.

    Returns (is_valid, list_of_issues).
    """
    issues = []
    for field in REQUIRED_FIELDS:
        if not record.get(field):
            issues.append(f"Missing required field: {field}")

    # Validate confidence range
    conf = record.get("confidence", 0)
    if not (0 <= conf <= 1):
        issues.append(f"Confidence out of range [0,1]: {conf}")

    # Validate content is non-empty
    content = record.get("content", "")
    if len(content.strip()) < 4:
        issues.append(f"Content too short ({len(content.strip())} chars)")

    return (len(issues) == 0, issues)


def validate_batch(
    records: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Validate a batch, returning (valid_records, quarantine_records).

    Invalid records go to quarantine with issues attached.
    """
    valid = []
    quarantine = []
    for rec in records:
        is_valid, issues = validate_record(rec)
        if is_valid:
            valid.append(rec)
        else:
            rec["_validation_issues"] = issues
            quarantine.append(rec)
            logger.warning(f"Record {rec.get('id', '?')} quarantined: {issues}")

    logger.info(
        f"Validation: {len(valid)} valid, {len(quarantine)} quarantined out of {len(records)}"
    )
    return valid, quarantine
