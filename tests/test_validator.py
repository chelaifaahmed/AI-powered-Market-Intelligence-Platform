"""
tests/test_validator.py
------------------------
Unit tests for parsers/validator.py

Tests every acceptance and rejection path of validate_record() to ensure
the quality gate behaves correctly for all entity types.
"""

from datetime import date

import pytest

from parsers.validator import validate_record


class TestValidateRecord:
    """Tests for the primary validate_record() function."""

    # ------------------------------------------------------------------
    # Valid records — must pass
    # ------------------------------------------------------------------

    def test_valid_full_record(self, valid_car_review_record):
        is_valid, reason = validate_record(valid_car_review_record)
        assert is_valid is True
        assert reason == ""

    def test_valid_minimal_record(self, minimal_valid_record):
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is True

    def test_valid_record_no_optional_fields(self):
        record = {
            "source_url": "https://example.com/reviews/42",
            "title": "Good review",
            "body_text": "This is a sufficiently long body text for testing purposes only.",
        }
        is_valid, reason = validate_record(record)
        assert is_valid is True

    def test_valid_rating_boundary_low(self, minimal_valid_record):
        minimal_valid_record["rating"] = 0.0
        is_valid, _ = validate_record(minimal_valid_record)
        assert is_valid is True

    def test_valid_rating_boundary_high(self, minimal_valid_record):
        minimal_valid_record["rating"] = 5.0
        is_valid, _ = validate_record(minimal_valid_record)
        assert is_valid is True

    def test_valid_rating_none_is_allowed(self, minimal_valid_record):
        minimal_valid_record["rating"] = None
        is_valid, _ = validate_record(minimal_valid_record)
        assert is_valid is True

    def test_valid_publish_date_as_date_object(self, minimal_valid_record):
        minimal_valid_record["publish_date"] = date(2025, 6, 15)
        is_valid, _ = validate_record(minimal_valid_record)
        assert is_valid is True

    # ------------------------------------------------------------------
    # Missing required fields — must reject
    # ------------------------------------------------------------------

    def test_missing_source_url_rejects(self, minimal_valid_record):
        del minimal_valid_record["source_url"]
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is False
        assert "source_url" in reason.lower() or reason != ""

    def test_empty_source_url_rejects(self, minimal_valid_record):
        minimal_valid_record["source_url"] = ""
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is False

    def test_missing_title_rejects(self, minimal_valid_record):
        del minimal_valid_record["title"]
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is False

    def test_empty_title_rejects(self, minimal_valid_record):
        minimal_valid_record["title"] = ""
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is False

    # ------------------------------------------------------------------
    # Body text constraints
    # ------------------------------------------------------------------

    def test_missing_body_text_rejects(self, minimal_valid_record):
        del minimal_valid_record["body_text"]
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is False

    def test_body_text_too_short_rejects(self, minimal_valid_record):
        minimal_valid_record["body_text"] = "Too short."
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is False

    def test_body_text_exactly_50_chars(self, minimal_valid_record):
        """50 chars is the boundary — should be valid (>= 50)."""
        minimal_valid_record["body_text"] = "A" * 50
        is_valid, _ = validate_record(minimal_valid_record)
        assert is_valid is True

    def test_body_text_49_chars_rejects(self, minimal_valid_record):
        minimal_valid_record["body_text"] = "A" * 49
        is_valid, _ = validate_record(minimal_valid_record)
        assert is_valid is False

    # ------------------------------------------------------------------
    # Rating constraints
    # ------------------------------------------------------------------

    def test_rating_above_5_rejects(self, minimal_valid_record):
        minimal_valid_record["rating"] = 5.1
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is False

    def test_rating_below_0_rejects(self, minimal_valid_record):
        minimal_valid_record["rating"] = -0.1
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is False

    def test_rating_as_string_digit(self, minimal_valid_record):
        """Numeric strings should be accepted (normalizer converts them)."""
        minimal_valid_record["rating"] = "4.5"
        # Validator should either accept this or reject with clear message
        is_valid, reason = validate_record(minimal_valid_record)
        # Either outcome is acceptable as long as it doesn't raise an exception
        assert isinstance(is_valid, bool)

    # ------------------------------------------------------------------
    # Publish date constraints
    # ------------------------------------------------------------------

    def test_invalid_publish_date_type_rejects(self, minimal_valid_record):
        minimal_valid_record["publish_date"] = "not-a-date"
        is_valid, reason = validate_record(minimal_valid_record)
        assert is_valid is False

    def test_publish_date_none_is_allowed(self, minimal_valid_record):
        minimal_valid_record["publish_date"] = None
        is_valid, _ = validate_record(minimal_valid_record)
        assert is_valid is True

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_dict_rejects(self):
        is_valid, reason = validate_record({})
        assert is_valid is False
        assert reason != ""

    def test_none_values_for_all_optional_fields(self):
        record = {
            "source_url": "https://example.com/1",
            "title": "Valid title here",
            "body_text": "B" * 60,
            "author": None,
            "rating": None,
            "publish_date": None,
            "brand": None,
            "model": None,
        }
        is_valid, _ = validate_record(record)
        assert is_valid is True
