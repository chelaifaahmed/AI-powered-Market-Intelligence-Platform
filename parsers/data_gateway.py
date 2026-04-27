"""
parsers/data_gateway.py
-----------------------
Centralized cleaning layer that every scraper must pass raw field dicts through
before inserting into a domain table (CarReview, InsuranceReview, MarketTrendArticle).

Usage:
    from parsers.data_gateway import clean_article, clean_car_review, clean_insurance_review

    cleaned = clean_article({"title": ..., "source_url": ..., ...})
    if cleaned is None:
        return False   # record rejected — skip insert
    # build ORM object from `cleaned` values

Returns None when minimum quality checks fail; otherwise returns a new dict
with all text fields normalized, ratings validated, and dates coerced.
Deduplication logic stays in each scraper (hash schemes differ per source).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from parsers.normalizer import normalize_date, normalize_rating, normalize_text

logger = logging.getLogger("parsers.data_gateway")

_MIN_REVIEW_LEN = 10   # absolute floor for review/complaint body
_MIN_ARTICLE_LEN = 20  # articles shorter than this are usually API noise


def clean_article(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normalize and validate a dict before it becomes a MarketTrendArticle row.
    Returns None if minimum quality requirements are not met.
    """
    title = normalize_text(raw.get("title"))
    source_url = normalize_text(raw.get("source_url"))

    if not title or not source_url:
        logger.debug("Rejected article: missing title or source_url")
        return None

    body = normalize_text(raw.get("body_text"))
    if body and len(body) < _MIN_ARTICLE_LEN:
        body = None  # too short to be useful; store null rather than noise

    author = normalize_text(raw.get("author"))

    pub_date = raw.get("publication_date")
    if isinstance(pub_date, str):
        pub_date = normalize_date(pub_date)

    return {
        **raw,
        "title": title[:500],
        "source_url": source_url,
        "body_text": body[:3000] if body else None,
        "author": author,
        "publication_date": pub_date,
    }


def clean_car_review(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normalize and validate a dict before it becomes a CarReview row.
    Returns None if minimum quality requirements are not met.
    """
    review_text = normalize_text(raw.get("review_text") or raw.get("text"))
    if not review_text or len(review_text) < _MIN_REVIEW_LEN:
        logger.debug("Rejected car review: body too short")
        return None

    source_url = normalize_text(raw.get("source_url"))
    if not source_url:
        logger.debug("Rejected car review: missing source_url")
        return None

    rating = _safe_rating(raw.get("rating"))

    review_date = raw.get("review_date")
    if isinstance(review_date, str):
        review_date = normalize_date(review_date)

    return {
        **raw,
        "review_text": review_text[:2000],
        "review_title": normalize_text(raw.get("review_title") or raw.get("title")),
        "author": normalize_text(raw.get("author")),
        "source_url": source_url,
        "rating": rating,
        "review_date": review_date,
    }


def clean_insurance_review(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normalize and validate a dict before it becomes an InsuranceReview row.
    Returns None if minimum quality requirements are not met.
    """
    review_text = normalize_text(raw.get("review_text") or raw.get("text"))
    if not review_text or len(review_text) < _MIN_REVIEW_LEN:
        logger.debug("Rejected insurance review: body too short")
        return None

    source_url = normalize_text(raw.get("source_url"))
    if not source_url:
        logger.debug("Rejected insurance review: missing source_url")
        return None

    rating = _safe_rating(raw.get("rating"))

    review_date = raw.get("review_date")
    if isinstance(review_date, str):
        review_date = normalize_date(review_date)

    return {
        **raw,
        "review_text": review_text[:2000],
        "review_title": normalize_text(raw.get("review_title") or raw.get("title")),
        "author": normalize_text(raw.get("author")),
        "source_url": source_url,
        "rating": rating,
        "review_date": review_date,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_rating(raw_rating: Any) -> Optional[float]:
    """Normalize a rating value and clamp it to [0, 5]. Returns None if invalid."""
    if raw_rating is None:
        return None
    normalized = normalize_rating(str(raw_rating))
    if normalized is None:
        return None
    # Drop ratings outside the allowed range rather than rejecting the whole record
    return normalized if 0.0 <= normalized <= 5.0 else None
