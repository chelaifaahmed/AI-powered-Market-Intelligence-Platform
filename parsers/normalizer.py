"""
parsers/normalizer.py
---------------------
STEP 6 — Field Normalisation

Merges extraction results from schema, DOM, and LLM passes,
then normalises each field to a canonical form ready for DB insertion.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parsers.normalizer")

# ---------------------------------------------------------------------------
# Legal suffix noise to strip from company names
# ---------------------------------------------------------------------------
_LEGAL_SUFFIX_RE = re.compile(
    r"\b(inc\.?|incorporated|llc\.?|ltd\.?|limited|plc\.?|corp\.?|corporation|"
    r"s\.a\.?|gmbh|b\.v\.?|ag|n\.v\.?|oy|as|a\/s|sarl|sas|spa)\b\.?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Public normalisation helpers
# ---------------------------------------------------------------------------

def normalize_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return re.sub(r"\s+", " ", text).strip()


def normalize_rating(rating: Optional[str]) -> Optional[float]:
    if not rating:
        return None
    try:
        # Extract first number found
        match = re.search(r"(\d+\.?\d*)", rating)
        if match:
            val = float(match.group(1))
            if 0 <= val <= 100: # Broad range, validator handles specific 1-5
                return val
    except Exception:
        pass
    return None


def normalize_date(raw: Optional[str]) -> Optional[date]:
    """Parse a date string into a Python date, or return None."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        from dateutil import parser as du_parser  # type: ignore
        return du_parser.parse(raw, fuzzy=True).date()
    except Exception:
        pass
    return None


def merge_extractions(
    schema_entities: List[Dict[str, Any]],
    dom: Dict[str, Any],
    llm: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge extractions into a unified automotive intelligence dict.
    """
    # Simply combine all for the orchestrator to decide
    return {
        "schema": schema_entities,
        "dom": dom,
        "llm": llm,
    }


def normalise_results(raw_merged: Dict[str, Any], source_url: str) -> Dict[str, Any]:
    """
    Apply normalisation to merged results.
    """
    dom = raw_merged.get("dom", {})
    llm = raw_merged.get("llm", {})
    
    # Priority: LLM often better for structured specs, DOM for raw counts
    brand = normalize_text(llm.get("vehicle_brand") or dom.get("brand"))
    model = normalize_text(llm.get("vehicle_model") or dom.get("model"))
    
    return {
        "brand": brand,
        "model": model,
        "rating": normalize_rating(llm.get("rating") or dom.get("rating")),
        "price_mention": normalize_text(llm.get("price_mention") or dom.get("price")),
        "source_url": source_url,
    }


def normalize_record(mapped_record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a mapped schema record into canonical DB-ready fields."""
    record = dict(mapped_record)
    record["title"] = normalize_text(record.get("title"))
    record["author"] = normalize_text(record.get("author"))
    record["body_text"] = normalize_text(record.get("body_text"))
    record["brand"] = normalize_text(record.get("brand"))
    record["model"] = normalize_text(record.get("model"))
    record["product_name"] = normalize_text(record.get("product_name"))
    record["rating"] = normalize_rating(str(record.get("rating")) if record.get("rating") is not None else None)
    record["publish_date"] = normalize_date(str(record.get("publish_date")) if record.get("publish_date") else None)
    record["source_url"] = normalize_text(record.get("source_url"))
    return record
