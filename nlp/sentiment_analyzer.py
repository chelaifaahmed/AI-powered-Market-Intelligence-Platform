"""
nlp/sentiment_analyzer.py
--------------------------
Transformer-based sentiment analyzer using DistilBERT fine-tuned on SST-2.

Model: distilbert-base-uncased-finetuned-sst-2-english (~67 MB)
Downloaded automatically from HuggingFace on first call and cached locally.

Public API (unchanged):
    analyze_sentiment(text: str) -> Tuple[str, float]
        Returns (label, score) where:
          label : "positive" | "neutral" | "negative"
          score : float in [-1.0, +1.0]
                  positive → +confidence, negative → -confidence,
                  neutral  → value near 0

Neutral threshold:
    If the model's confidence for either class is below NEUTRAL_THRESHOLD
    (default 0.65), the prediction is too uncertain to call positive or
    negative, so we return "neutral" with the signed fractional score.

Fallback:
    If the transformer pipeline fails for any reason (import error, OOM,
    model download failure), the module falls back transparently to the
    original keyword-weighted rule-based analyzer so the rest of the
    pipeline keeps running.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger("nlp.sentiment_analyzer")

# ---------------------------------------------------------------------------
# Model ID and thresholds
# ---------------------------------------------------------------------------
_MODEL_ID = "distilbert-base-uncased-finetuned-sst-2-english"
_NEUTRAL_THRESHOLD = 0.65   # confidence below this → "neutral"
_MAX_TOKENS = 512           # DistilBERT max input length

# ---------------------------------------------------------------------------
# Lazy singleton — model loaded once, reused for every call
# ---------------------------------------------------------------------------
_sentiment_pipeline = None
_pipeline_failed = False     # set True if loading fails so we skip retries


def _get_pipeline():
    """Return the cached HuggingFace pipeline, loading it on first call."""
    global _sentiment_pipeline, _pipeline_failed

    if _sentiment_pipeline is not None:
        return _sentiment_pipeline
    if _pipeline_failed:
        return None

    try:
        from transformers import pipeline as hf_pipeline
        logger.info("Loading sentiment model '%s' (first call — may download ~67 MB)…", _MODEL_ID)
        _sentiment_pipeline = hf_pipeline(
            "sentiment-analysis",
            model=_MODEL_ID,
            truncation=True,
            max_length=_MAX_TOKENS,
        )
        logger.info("Sentiment model loaded successfully.")
        return _sentiment_pipeline
    except Exception as exc:
        _pipeline_failed = True
        logger.warning("Failed to load transformer model — falling back to rule-based: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Fallback: original keyword-weighted scorer
# ---------------------------------------------------------------------------
_POSITIVE_WEIGHTS = {
    "excellent": 1.0, "reliable": 0.9, "smooth": 0.8, "great": 0.7,
    "efficient": 0.7, "good": 0.5, "comfortable": 0.5, "improved": 0.4,
}
_NEGATIVE_WEIGHTS = {
    "terrible": 1.0, "broken": 0.9, "unreliable": 0.9, "expensive": 0.8,
    "delayed": 0.8, "delay": 0.6, "bad": 0.6, "poor": 0.6,
    "problem": 0.5, "issue": 0.4,
}


def _rule_based_sentiment(text: str) -> Tuple[str, float]:
    """Original keyword-weighted fallback. Kept for resilience."""
    try:
        from nlp.text_preprocessor import remove_stopwords, tokenize
        toks = remove_stopwords(tokenize(text), min_len=2)
    except Exception:
        toks = text.lower().split()

    if not toks:
        return "neutral", 0.0

    pos = sum(_POSITIVE_WEIGHTS.get(t, 0.0) for t in toks)
    neg = sum(_NEGATIVE_WEIGHTS.get(t, 0.0) for t in toks)
    total = pos + neg
    score = 0.0 if total == 0 else (pos - neg) / total
    score = max(-1.0, min(1.0, score))

    if score > 0.2:
        return "positive", round(score, 4)
    if score < -0.2:
        return "negative", round(score, 4)
    return "neutral", round(score, 4)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def analyze_sentiment(text: str) -> Tuple[str, float]:
    """
    Analyze the sentiment of *text*.

    Returns:
        (label, score)
        label — "positive" | "neutral" | "negative"
        score — float in [-1.0, +1.0]
    """
    if not text or not text.strip():
        return "neutral", 0.0

    pipe = _get_pipeline()

    if pipe is None:
        # transformer unavailable — use rule-based fallback
        return _rule_based_sentiment(text)

    try:
        result = pipe(text[:2000])[0]   # cap input chars to avoid very slow runs
        label_raw: str = result["label"].upper()   # "POSITIVE" or "NEGATIVE"
        confidence: float = float(result["score"])  # 0.0 – 1.0

        # Map to signed score in [-1, 1]
        signed_score = confidence if label_raw == "POSITIVE" else -confidence

        # Apply neutral threshold
        if confidence < _NEUTRAL_THRESHOLD:
            # Model is uncertain — call it neutral but keep the small score
            return "neutral", round(signed_score, 4)

        label = "positive" if label_raw == "POSITIVE" else "negative"
        return label, round(signed_score, 4)

    except Exception as exc:
        logger.warning("Transformer inference failed (%s) — using rule-based fallback", exc)
        return _rule_based_sentiment(text)
