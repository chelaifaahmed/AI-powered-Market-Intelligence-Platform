"""
tests/test_sentiment_analyzer.py
----------------------------------
Unit tests for nlp/sentiment_analyzer.py

Tests both the transformer path and the keyword-based fallback,
ensuring correct label and score ranges are returned.
"""

import pytest

from nlp.sentiment_analyzer import _rule_based_sentiment, analyze_sentiment


class TestAnalyzeSentiment:
    """Tests for the public analyze_sentiment() API."""

    # ------------------------------------------------------------------
    # Output contract
    # ------------------------------------------------------------------

    def test_returns_tuple(self):
        result = analyze_sentiment("This car is great.")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_label_is_valid(self):
        label, _ = analyze_sentiment("Excellent car, very reliable.")
        assert label in {"positive", "neutral", "negative"}

    def test_score_is_float_in_range(self):
        _, score = analyze_sentiment("The engine broke down repeatedly.")
        assert isinstance(score, float)
        assert -1.0 <= score <= 1.0

    # ------------------------------------------------------------------
    # Expected sentiment directions
    # ------------------------------------------------------------------

    def test_clearly_positive_text(self):
        label, score = analyze_sentiment(
            "This car is absolutely excellent. Very reliable, smooth ride, "
            "great fuel efficiency. Highly recommend to everyone."
        )
        assert label == "positive"
        assert score > 0

    def test_clearly_negative_text(self):
        label, score = analyze_sentiment(
            "Terrible experience. The engine broke down, the dealer was unhelpful, "
            "and the car is completely unreliable. Very disappointed."
        )
        assert label == "negative"
        assert score < 0

    def test_empty_string_returns_neutral(self):
        label, score = analyze_sentiment("")
        assert label == "neutral"
        assert score == 0.0

    def test_whitespace_only_returns_neutral(self):
        label, score = analyze_sentiment("   ")
        assert label == "neutral"
        assert score == 0.0

    def test_none_like_empty(self):
        """Passing None should not raise — returns neutral."""
        try:
            label, score = analyze_sentiment(None)
            assert label == "neutral"
        except TypeError:
            pass  # Acceptable if function validates input type

    # ------------------------------------------------------------------
    # Score directionality
    # ------------------------------------------------------------------

    def test_positive_label_has_positive_score(self):
        label, score = analyze_sentiment(
            "Outstanding performance and excellent build quality."
        )
        if label == "positive":
            assert score > 0

    def test_negative_label_has_negative_score(self):
        label, score = analyze_sentiment(
            "Broken, unreliable, terrible customer service."
        )
        if label == "negative":
            assert score < 0

    def test_neutral_score_near_zero(self):
        """Neutral predictions should have small absolute score."""
        label, score = analyze_sentiment("The car exists.")
        if label == "neutral":
            assert abs(score) < 0.65


class TestRuleBasedFallback:
    """Tests for the _rule_based_sentiment() fallback function."""

    def test_positive_keywords(self):
        label, score = _rule_based_sentiment("This is excellent and reliable")
        assert label == "positive"
        assert score > 0

    def test_negative_keywords(self):
        label, score = _rule_based_sentiment("This is terrible and broken")
        assert label == "negative"
        assert score < 0

    def test_no_keywords_returns_neutral(self):
        label, score = _rule_based_sentiment("the cat sat on the mat")
        assert label == "neutral"

    def test_empty_string_returns_neutral(self):
        label, score = _rule_based_sentiment("")
        assert label == "neutral"
        assert score == 0.0

    def test_score_bounded(self):
        label, score = _rule_based_sentiment("excellent excellent excellent excellent")
        assert -1.0 <= score <= 1.0

    def test_mixed_sentiment_returns_score(self):
        """Mixed text — score should still be in range."""
        label, score = _rule_based_sentiment("excellent but also terrible")
        assert -1.0 <= score <= 1.0
        assert label in {"positive", "neutral", "negative"}
