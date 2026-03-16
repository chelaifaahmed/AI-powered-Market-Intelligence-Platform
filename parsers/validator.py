"""
parsers/validator.py
--------------------
STEP 7 — Record Validation & Quality Gate

Enforces minimum quality thresholds before a record is allowed
into the database.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("parsers.validator")

# Minimum body length required for accepted records.
_MIN_DESCRIPTION_LEN = 50

def validate_record(record: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate normalized records before persistence."""
    title = (record.get("title") or "").strip()
    body = (record.get("body_text") or "").strip()
    rating = record.get("rating")
    publish_date: Optional[date] = record.get("publish_date")
    source_url = (record.get("source_url") or "").strip()

    if not source_url:
        return False, "source_url is empty"

    if not title:
        return False, "title is empty"

    if len(body) < _MIN_DESCRIPTION_LEN:
        return False, "body_text too short"

    if rating is not None and not (0.0 <= float(rating) <= 5.0):
        return False, "rating out of allowed range [0,5]"

    if publish_date is not None and not isinstance(publish_date, date):
        return False, "publish_date is invalid"

    return True, ""


def validate(record: Dict[str, Any]) -> Tuple[bool, str]:
    """Backward-compatible alias for older imports."""
    return validate_record(record)
