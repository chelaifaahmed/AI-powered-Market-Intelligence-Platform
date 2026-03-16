"""Simple top-k keyword extraction."""

from __future__ import annotations

from collections import Counter
from typing import List

from nlp.text_preprocessor import remove_stopwords, tokenize


def extract_keywords(text: str, limit: int = 10) -> List[str]:
    """Extract top keywords using token filtering and bigram support."""
    tokens = remove_stopwords(tokenize(text or ""), min_len=3)
    if not tokens:
        return []

    unigram_counts = Counter(tokens)
    bigrams = [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]
    bigram_counts = Counter(bigrams)

    scored = Counter()
    for term, c in unigram_counts.items():
        scored[term] += c
    for term, c in bigram_counts.items():
        # Slight preference for recurring phrases.
        scored[term] += c * 1.5

    return [w for w, _ in scored.most_common(limit)]
