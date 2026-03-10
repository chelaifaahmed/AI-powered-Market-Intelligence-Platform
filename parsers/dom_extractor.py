"""
parsers/dom_extractor.py
------------------------
STEP 3 — DOM Heuristic Extraction

Uses CSS selectors and regex patterns to locate automotive intelligence
fields within lightly cleaned HTML. This pass provides a baseline that schema_extractor
can override, or that LLM fallback supplements.

Extraction priority within each field:
    1. Specific data attributes (data-company, data-location, …)
    2. Known semantic CSS classes / ids
    3. Generic structural selectors (h1, meta tags)
    4. Regex patterns applied to full text

All fields may return None — no field is mandatory at this stage.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger("parsers.dom_extractor")

# ---------------------------------------------------------------------------
# Selector maps — tried in order; first non-empty match wins
# ---------------------------------------------------------------------------

_BRAND_SELECTORS = [
    ".brand", ".manufacturer", "[data-brand]",
    ".vehicle-brand", "span[class*='brand']",
]

_MODEL_SELECTORS = [
    ".model", ".vehicle-model", "[data-model]",
    "h1.model-name", "span[class*='model']",
]

_RATING_SELECTORS = [
    ".rating", ".score", ".average-rating",
    "[data-rating]", "span[class*='rating']",
]

_PRICE_SELECTORS = [
    ".price", ".msrp", ".listed-price",
    "[data-price]", ".vehicle-price",
]


def _first_text(soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
    """Try each selector and return the first non-empty text found."""
    for sel in selectors:
        try:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(separator=" ", strip=True)
                if text:
                    return text
        except Exception:
            continue
    return None


def extract_from_dom(clean_html: str, source_url: str = "") -> Dict[str, Any]:
    """
    Heuristic DOM-based extraction of automotive intelligence fields.

    Args:
        clean_html: Lightly cleaned HTML (boilerplate mostly removed).
        source_url: Original source URL.

    Returns:
        Dict with discovered automotive fields.
    """
    if not clean_html:
        return {}

    try:
        soup = BeautifulSoup(clean_html, "lxml")
    except Exception as exc:
        logger.error("BS4 parse error in dom_extractor: %s", exc)
        return {}

    result: Dict[str, Any] = {
        "brand": _first_text(soup, _BRAND_SELECTORS),
        "model": _first_text(soup, _MODEL_SELECTORS),
        "rating": _first_text(soup, _RATING_SELECTORS),
        "price": _first_text(soup, _PRICE_SELECTORS),
        "title": _first_text(soup, ["h1", "title"]),
        "body_text": soup.get_text(separator=" ", strip=True),
    }

    return result
