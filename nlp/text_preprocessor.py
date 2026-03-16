"""Shared text preprocessing helpers for NLP modules."""

from __future__ import annotations

import re
from typing import List, Set

_STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "with", "is", "are",
    "was", "were", "be", "been", "this", "that", "it", "as", "at", "by", "from", "but",
    "not", "you", "we", "they", "he", "she", "i", "my", "our", "their", "his", "her",
    "your", "yours", "ours", "them", "its", "if", "then", "than", "into", "about", "over",
}


def clean_text(text: str) -> str:
    """Lowercase text and remove punctuation/noise while preserving spaces."""
    if not text:
        return ""
    cleaned = text.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def tokenize(text: str) -> List[str]:
    """Tokenize cleaned text into alphanumeric tokens."""
    cleaned = clean_text(text)
    if not cleaned:
        return []
    return re.findall(r"[a-z0-9]+", cleaned)


def remove_stopwords(tokens: List[str], min_len: int = 3) -> List[str]:
    """Filter stopwords and short tokens."""
    return [t for t in tokens if t not in _STOPWORDS and len(t) >= min_len]
