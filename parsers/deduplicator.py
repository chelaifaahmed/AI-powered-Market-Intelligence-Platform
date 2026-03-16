"""
parsers/deduplicator.py
-----------------------
STEP 8 - Deduplication

Prevents duplicate automotive/insurance records from being inserted twice.

Strategy (priority order):
    1. content_hash match  (SHA-256 of title|company|location) - exact
    2. title + company + location triple match - catches re-scrapes with
       minor HTML changes that produce different hashes
"""

from __future__ import annotations

import hashlib
import logging
from difflib import SequenceMatcher
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("parsers.deduplicator")


def compute_content_hash(
    brand: Optional[str],
    model: Optional[str],
    url: str,
) -> str:
    """
    Compute a SHA-256 hex digest for deduplication.
    """
    parts = [
        (brand or "").strip().lower(),
        (model or "").strip().lower(),
        url.strip().lower(),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_duplicate(
    session: Session,
    content_hash: str,
    table_class: Any,
) -> bool:
    """
    Check if a record with the same content_hash exists in the specified table.
    """
    existing = (
        session.query(table_class.id)
        .filter(table_class.content_hash == content_hash)
        .first()
    )
    return existing is not None


def deduplicate_record(
    session: Session,
    table_class: Any,
    source_url: str,
    title: Optional[str],
    content_hash: Optional[str],
    similarity_threshold: float = 0.95,
) -> bool:
    """Return True when record is duplicate by URL/hash/title similarity."""
    # URL-level deduplication is the cheapest and strongest signal.
    if hasattr(table_class, "source_url"):
        by_url = (
            session.query(table_class.id)
            .filter(table_class.source_url == source_url)
            .first()
        )
        if by_url is not None:
            return True

    if content_hash and hasattr(table_class, "content_hash"):
        if is_duplicate(session, content_hash, table_class):
            return True

    if title and hasattr(table_class, "review_title"):
        candidates = (
            session.query(table_class.review_title)
            .filter(table_class.source_url == source_url)
            .limit(20)
            .all()
        )
        for (existing_title,) in candidates:
            if not existing_title:
                continue
            score = SequenceMatcher(None, title.lower(), existing_title.lower()).ratio()
            if score >= similarity_threshold:
                return True

    if title and hasattr(table_class, "title"):
        candidates = (
            session.query(table_class.title)
            .filter(table_class.source_url == source_url)
            .limit(20)
            .all()
        )
        for (existing_title,) in candidates:
            if not existing_title:
                continue
            score = SequenceMatcher(None, title.lower(), existing_title.lower()).ratio()
            if score >= similarity_threshold:
                return True

    return False
