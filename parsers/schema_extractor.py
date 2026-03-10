"""
parsers/schema_extractor.py
----------------------------
STEP 4 — JSON-LD / Structured Data Extraction

Parses <script type="application/ld+json"> blocks from HTML
and returns all found Schema.org entities.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger("parsers.schema_extractor")


def _find_entities(obj: Any) -> List[Dict]:
    """Recursively search for Schema.org entity nodes."""
    results: List[Dict] = []
    if isinstance(obj, dict):
        obj_type = obj.get("@type", "")
        if obj_type:
            results.append(obj)
        for key, val in obj.items():
            if isinstance(val, (dict, list)):
                results.extend(_find_entities(val))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_entities(item))
    return results


def extract_from_schema(html: str) -> List[Dict[str, Any]]:
    """
    Parse JSON-LD from HTML and return all found Schema.org entities.

    Args:
        html: Raw or lightly cleaned HTML string.

    Returns:
        List of extraction dicts found in JSON-LD.
    """
    if not html:
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as exc:
        logger.debug("BS4 parse failed in schema_extractor: %s", exc)
        return []

    ld_scripts = soup.find_all(
        "script", attrs={"type": "application/ld+json"}
    )
    
    entities = []
    for script_tag in ld_scripts:
        try:
            data = json.loads(script_tag.string or "")
            entities.extend(_find_entities(data))
        except (json.JSONDecodeError, TypeError) as exc:
            logger.debug("JSON-LD parse error: %s", exc)
            continue

    return entities
