"""
nlp/sentiment_analyzer.py
--------------------------
Transformer-based sentiment analyzer with a three-tier model hierarchy:

  Tier 1 (primary) — models/sentiment-automotive-v1/
    Domain-adapted distilbert-base-multilingual-cased, fine-tuned on
    automotive and insurance reviews via LLM-assisted labeling (Groq
    Llama 3.3-70b).  Supports English and French.  3-class output:
    negative / neutral / positive.

  Tier 2 (fallback) — distilbert-base-uncased-finetuned-sst-2-english
    Generic SST-2 model from HuggingFace (~67 MB).  Used when the
    fine-tuned model is not yet available (pre-training-run state).
    Binary output mapped to 3-class with a neutral confidence threshold.

  Tier 3 (last resort) — keyword-weighted rule-based scorer
    Pure Python; no dependencies.  Activated when both transformer tiers
    fail (OOM, download failure, etc.).

Public API (unchanged from previous version):
    analyze_sentiment(text: str) -> Tuple[str, float]
        Returns (label, score) where:
          label : "positive" | "neutral" | "negative"
          score : float in [-1.0, +1.0]
                  positive → +confidence, negative → -confidence,
                  neutral  → value near 0
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger("nlp.sentiment_analyzer")

# ---------------------------------------------------------------------------
# Model paths and thresholds
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
# v3 (2026-04-23): Protocol 2 macro-F1=0.834 vs SST-2 0.528 — enabled in production.
# Trained on 600 balanced samples (200×3) including 300 Yelp 3-star dealership reviews.
_FINETUNED_DIR = _PROJECT_ROOT / "models" / "sentiment-automotive-v1"

_SST2_MODEL_ID       = "distilbert-base-uncased-finetuned-sst-2-english"
_NEUTRAL_THRESHOLD   = 0.65   # SST-2 confidence below this → "neutral"
_MAX_TOKENS_SST2     = 512
_MAX_TOKENS_FINETUNED = 256

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_primary_pipeline  = None    # fine-tuned model (Tier 1)
_fallback_pipeline = None    # SST-2 (Tier 2)
_primary_failed    = False
_fallback_failed   = False

_FINETUNED_LABEL_MAP = {"negative": "negative", "neutral": "neutral",
                         "positive": "positive",
                         # handle uppercase labels just in case
                         "NEGATIVE": "negative", "NEUTRAL": "neutral",
                         "POSITIVE": "positive",
                         # handle LABEL_0/1/2 if model config is missing id2label
                         "LABEL_0": "negative", "LABEL_1": "neutral",
                         "LABEL_2": "positive"}


def _get_primary_pipeline():
    """Load the domain fine-tuned model (Tier 1) on first call."""
    global _primary_pipeline, _primary_failed

    if _primary_pipeline is not None:
        return _primary_pipeline
    if _primary_failed:
        return None
    if _FINETUNED_DIR is None or not _FINETUNED_DIR.exists():
        # Fine-tuned model disabled or not yet trained — fall to Tier 2
        return None

    try:
        from transformers import pipeline as hf_pipeline
        logger.info(
            "Loading domain fine-tuned sentiment model from '%s' …",
            _FINETUNED_DIR,
        )
        _primary_pipeline = hf_pipeline(
            "text-classification",
            model=str(_FINETUNED_DIR),
            tokenizer=str(_FINETUNED_DIR),
            truncation=True,
            max_length=_MAX_TOKENS_FINETUNED,
        )
        logger.info("Fine-tuned sentiment model loaded successfully (Tier 1).")
        return _primary_pipeline
    except Exception as exc:
        _primary_failed = True
        logger.warning(
            "Failed to load fine-tuned model — will use SST-2 fallback: %s", exc
        )
        return None


def _get_fallback_pipeline():
    """Load SST-2 (Tier 2) on first call."""
    global _fallback_pipeline, _fallback_failed

    if _fallback_pipeline is not None:
        return _fallback_pipeline
    if _fallback_failed:
        return None

    try:
        from transformers import pipeline as hf_pipeline
        logger.info(
            "Loading SST-2 fallback model '%s' (may download ~67 MB) …",
            _SST2_MODEL_ID,
        )
        _fallback_pipeline = hf_pipeline(
            "sentiment-analysis",
            model=_SST2_MODEL_ID,
            truncation=True,
            max_length=_MAX_TOKENS_SST2,
        )
        logger.info("SST-2 fallback model loaded (Tier 2).")
        return _fallback_pipeline
    except Exception as exc:
        _fallback_failed = True
        logger.warning(
            "Failed to load SST-2 model — falling back to rule-based: %s", exc
        )
        return None


# ---------------------------------------------------------------------------
# Tier 3 — keyword-weighted rule-based fallback
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
# Public API
# ---------------------------------------------------------------------------

def analyze_sentiment(text: str) -> Tuple[str, float]:
    """
    Analyze the sentiment of *text*.

    Returns:
        (label, score)
        label — "positive" | "neutral" | "negative"
        score — float in [-1.0, +1.0]

    Model tier used is logged at INFO level.
    """
    if not text or not text.strip():
        return "neutral", 0.0

    # ----- Tier 1: domain fine-tuned model -----
    primary = _get_primary_pipeline()
    if primary is not None:
        try:
            result     = primary(text[:2000])[0]
            label_raw  = result["label"]
            confidence = float(result["score"])
            label = _FINETUNED_LABEL_MAP.get(label_raw, "neutral")
            if label == "positive":
                return "positive", round(confidence, 4)
            if label == "negative":
                return "negative", round(-confidence, 4)
            return "neutral", round(
                confidence if confidence < 0.5 else 1 - confidence, 4
            )
        except Exception as exc:
            logger.warning("Fine-tuned inference failed (%s) — trying SST-2", exc)

    # ----- Tier 2: SST-2 generic model -----
    fallback = _get_fallback_pipeline()
    if fallback is not None:
        try:
            result     = fallback(text[:2000])[0]
            label_raw  = result["label"].upper()
            confidence = float(result["score"])
            signed_score = confidence if label_raw == "POSITIVE" else -confidence
            if confidence < _NEUTRAL_THRESHOLD:
                return "neutral", round(signed_score, 4)
            label = "positive" if label_raw == "POSITIVE" else "negative"
            return label, round(signed_score, 4)
        except Exception as exc:
            logger.warning(
                "SST-2 inference failed (%s) — using rule-based fallback", exc
            )

    # ----- Tier 3: rule-based -----
    return _rule_based_sentiment(text)


def active_model_tier() -> str:
    """Return a human-readable string indicating which tier is active."""
    if _get_primary_pipeline() is not None:
        return "Tier 1 — domain fine-tuned (sentiment-automotive-v1)"
    if _get_fallback_pipeline() is not None:
        return "Tier 2 — SST-2 generic baseline"
    return "Tier 3 — rule-based fallback"
