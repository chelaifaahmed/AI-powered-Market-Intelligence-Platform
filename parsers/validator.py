"""
parsers/validator.py
--------------------
STEP 7 — Record Validation & Quality Gate

Enforces minimum quality thresholds before a record is allowed
into the database.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger("parsers.validator")

# Minimum description length (characters) when title IS present
_MIN_DESCRIPTION_LEN = 200

def validate(record: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate an automotive intelligence record.
    """
    brand = record.get("brand")
    model = record.get("model")

    if not brand and not model:
        return False, "neither brand nor model identified"

    return True, ""
