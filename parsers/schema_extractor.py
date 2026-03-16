"""Schema extraction and mapping stage for parser pipeline."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

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


def map_to_schema(dom_data: Dict[str, Any], schema_entities: List[Dict[str, Any]], source_url: str) -> Dict[str, Any]:
    """Map extraction output to one platform entity schema candidate.

    Entity-type priority (highest → lowest):
      1. car_listing         — marketplace listing pages
      2. competitor_pricing  — insurance price-comparison pages
      3. market_trend_article
      4. insurance_review
      5. car_review          — default fallback
    """
    title = (dom_data.get("title") or "").lower()
    url = (source_url or "").lower()

    # --- Car marketplace listings ----------------------------------------
    is_listing = any(k in url for k in [
        "autoscout24", "autotrader", "cars.com", "cargurus",
        "leboncoin/voitures", "mobile.de", "/lst/",
    ]) or any(k in title for k in ["listing", "for sale", "used car", "buy car"])

    # --- Insurance competitor pricing ------------------------------------
    is_pricing = any(k in url for k in [
        "comparethemarket", "moneysupermarket", "confused.com",
        "gocompare", "insurancequotes", "getjerry",
    ]) or any(k in title for k in ["compare insurance", "car insurance quote", "insurance price"])

    # --- Existing entity types -------------------------------------------
    is_news = any(k in url for k in ["reuters", "bloomberg", "autonews", "cnn"]) or any(
        k in title for k in ["market", "news", "industry", "trend"]
    )
    is_insurance = any(k in url for k in [
        "insurance", "nerdwallet", "policy", "forbes.com/advisor/car-insurance"
    ]) or any(k in title for k in ["insurance", "policy", "premium", "insurer"])

    if is_listing:
        entity_type = "car_listing"
    elif is_pricing:
        entity_type = "competitor_pricing"
    elif is_news:
        entity_type = "market_trend_article"
    elif is_insurance:
        entity_type = "insurance_review"
    else:
        entity_type = "car_review"

    return {
        "entity_type": entity_type,
        "record": {
            "title": dom_data.get("title"),
            "author": dom_data.get("author"),
            "publish_date": dom_data.get("publish_date"),
            "body_text": dom_data.get("body_text"),
            "rating": dom_data.get("rating"),
            "product_name": dom_data.get("product_name") or dom_data.get("model"),
            "brand": dom_data.get("brand"),
            "model": dom_data.get("model"),
            "source_url": source_url,
            "schema_entities": schema_entities,
            # Listing/pricing supplemental fields (populated when available)
            "listing_price": dom_data.get("listing_price"),
            "mileage_km": dom_data.get("mileage_km"),
            "dealer_name": dom_data.get("dealer_name"),
            "city": dom_data.get("city"),
            "country": dom_data.get("country"),
            "coverage_type": dom_data.get("coverage_type"),
            "region": dom_data.get("region"),
        },
    }
