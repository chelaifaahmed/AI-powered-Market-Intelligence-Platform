"""DOM extraction stage for parser pipeline."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger("parsers.dom_extractor")

# Tried in order; first non-empty match wins.

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

_AUTHOR_SELECTORS = [
    "[name='author']",
    "[property='article:author']",
    ".author",
    ".byline",
    "[class*='author']",
]

_PUBLISH_DATE_SELECTORS = [
    "time[datetime]",
    "meta[property='article:published_time']",
    "meta[name='pubdate']",
    "meta[name='publish-date']",
]

_BODY_SELECTORS = [
    "article",
    "main",
    ".article-body",
    ".content",
    "[class*='article']",
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


def _first_attr(soup: BeautifulSoup, selectors: List[str], attr: str) -> Optional[str]:
    """Try each selector and return first non-empty attribute value."""
    for sel in selectors:
        try:
            el = soup.select_one(sel)
            if not el:
                continue
            val = el.get(attr)
            if isinstance(val, str) and val.strip():
                return val.strip()
        except Exception:
            continue
    return None


def extract_dom(clean_html: str, source_url: str = "") -> Dict[str, Any]:
    """Extract core fields from cleaned HTML using DOM heuristics."""
    if not clean_html:
        return {}

    try:
        soup = BeautifulSoup(clean_html, "lxml")
    except Exception as exc:
        logger.error("BS4 parse error in dom_extractor: %s", exc)
        return {}

    publish_date = _first_attr(soup, _PUBLISH_DATE_SELECTORS, "datetime")
    if not publish_date:
        publish_date = _first_attr(soup, _PUBLISH_DATE_SELECTORS, "content")

    body_text = _first_text(soup, _BODY_SELECTORS)
    if not body_text:
        body_text = soup.get_text(separator=" ", strip=True)

    result: Dict[str, Any] = {
        "brand": _first_text(soup, _BRAND_SELECTORS),
        "model": _first_text(soup, _MODEL_SELECTORS),
        "rating": _first_text(soup, _RATING_SELECTORS),
        "price": _first_text(soup, _PRICE_SELECTORS),
        "title": _first_text(soup, ["h1", "title"]),
        "author": _first_text(soup, _AUTHOR_SELECTORS),
        "publish_date": publish_date,
        "product_name": _first_text(soup, ["h1", "h2", ".product-name", ".vehicle-model"]),
        "body_text": body_text,
        "source_url": source_url,
    }

    return result


def extract_from_dom(clean_html: str, source_url: str = "") -> Dict[str, Any]:
    """Backward-compatible alias for older imports."""
    return extract_dom(clean_html, source_url)
