"""Complaint category classifier for automotive and insurance domains."""

from __future__ import annotations

from typing import Dict, List, Set

from nlp.text_preprocessor import clean_text

_COMPLAINT_KEYWORDS: Dict[str, Set[str]] = {
    "engine_issues": {
        "engine", "stall", "overheat", "oil leak", "misfire", "knocking", "transmission"
    },
    "battery_issues": {
        "battery", "charging", "range drop", "dead battery", "battery drain", "charge failure"
    },
    "claims_delays": {
        "claim delay", "claims delay", "slow claim", "pending claim", "claim pending", "late settlement"
    },
    "policy_pricing": {
        "premium increase", "policy cost", "overpriced", "rate hike", "high premium", "price increase"
    },
    "customer_service": {
        "rude", "unhelpful", "no response", "poor service", "bad support", "long wait"
    },
}


def classify_complaints(text: str) -> List[str]:
    """Return complaint categories detected in text."""
    low = clean_text(text or "")
    found: List[str] = []
    for category, words in _COMPLAINT_KEYWORDS.items():
        if any(w in low for w in words):
            found.append(category)
    return found
