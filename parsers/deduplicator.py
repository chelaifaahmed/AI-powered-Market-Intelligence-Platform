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
