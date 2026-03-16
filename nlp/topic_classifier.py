"""Keyword-driven topic classifier for reviews and market articles."""

from __future__ import annotations

from typing import Dict, List, Set

from nlp.text_preprocessor import clean_text, remove_stopwords, tokenize

_TOPIC_KEYWORDS: Dict[str, Set[str]] = {
    "pricing": {
        "price", "pricing", "cost", "expensive", "cheap", "premium", "quote", "msrp", "affordable"
    },
    "reliability": {
        "reliable", "reliability", "breakdown", "durable", "maintenance", "failure", "unreliable"
    },
    "fuel economy": {
        "fuel", "mpg", "consumption", "efficiency", "economy", "mileage", "range"
    },
    "insurance claims": {
        "claim", "claims", "settlement", "coverage", "reimbursement", "denied", "adjuster"
    },
    "customer service": {
        "support", "service", "agent", "representative", "response", "hotline", "staff"
    },
    "technology": {
        "technology", "software", "infotainment", "autonomous", "battery", "ev", "sensor", "update"
    },
}


def classify_topics(text: str) -> List[str]:
    """Return matched high-level topics from text."""
    low = clean_text(text or "")
    tokens = set(remove_stopwords(tokenize(low), min_len=3))
    topics: List[str] = []
    for topic, words in _TOPIC_KEYWORDS.items():
        if any(w in low for w in words) or any(w in tokens for w in words):
            topics.append(topic)
    return topics or ["general"]
