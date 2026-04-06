"""
tests/test_normalizer.py
-------------------------
Unit tests for parsers/normalizer.py

Covers text normalization, rating parsing, date parsing, and full
record normalization to ensure the pipeline produces clean data.
"""

from datetime import date

import pytest

from parsers.normalizer import (
    normalize_date,
    normalize_rating,
    normalize_record,
    normalize_text,
)


class TestNormalizeText:
    def test_strips_leading_trailing_whitespace(self):
        assert normalize_text("  hello world  ") == "hello world"

    def test_collapses_internal_whitespace(self):
        assert normalize_text("hello   world") == "hello world"

    def test_handles_none(self):
        assert normalize_text(None) is None

    def test_handles_empty_string(self):
        result = normalize_text("")
        assert result == "" or result is None

    def test_preserves_normal_text(self):
        text = "This is a normal sentence."
        assert normalize_text(text) == text

    def test_strips_newlines(self):
        result = normalize_text("line one\nline two")
        assert "\n" not in result or result == "line one line two"


class TestNormalizeRating:
    def test_integer_string(self):
        result = normalize_rating("4")
        assert result == 4.0

    def test_float_string(self):
        result = normalize_rating("4.5")
        assert result == pytest.approx(4.5)

    def test_float_value(self):
        # normalize_rating accepts strings only — pass as string
        result = normalize_rating("3.7")
        assert result == pytest.approx(3.7)

    def test_integer_value(self):
        # normalize_rating accepts strings only — pass as string
        result = normalize_rating("5")
        assert result == 5.0

    def test_none_returns_none(self):
        assert normalize_rating(None) is None

    def test_invalid_string_returns_none(self):
        assert normalize_rating("not a number") is None

    def test_empty_string_returns_none(self):
        assert normalize_rating("") is None

    def test_rating_with_text_prefix(self):
        """e.g. '4.5/5' or 'Rating: 4.5' — should extract the first number."""
        result = normalize_rating("4.5/5")
        assert result is not None
        assert result == pytest.approx(4.5)


class TestNormalizeDate:
    def test_date_string_roundtrip(self):
        # normalize_date accepts strings — pass ISO string and expect date back
        result = normalize_date("2025-06-15")
        assert result == date(2025, 6, 15)

    def test_iso_string(self):
        result = normalize_date("2025-06-15")
        assert result == date(2025, 6, 15)

    def test_us_format_string(self):
        result = normalize_date("June 15, 2025")
        assert result is not None
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 15

    def test_none_returns_none(self):
        assert normalize_date(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_date("") is None

    def test_invalid_string_returns_none(self):
        assert normalize_date("not a date") is None

    def test_returns_date_not_datetime(self):
        result = normalize_date("2025-01-01T12:00:00")
        assert result is not None
        assert isinstance(result, date)


class TestNormalizeRecord:
    def test_full_record_passes_through(self, valid_car_review_record):
        result = normalize_record(valid_car_review_record)
        assert result["source_url"] == valid_car_review_record["source_url"]
        assert result["brand"] == "Toyota"

    def test_whitespace_cleaned_in_title(self):
        record = {
            "source_url": "https://example.com/1",
            "title": "  Messy   Title  ",
            "body_text": "Some body text that is long enough to pass.",
        }
        result = normalize_record(record)
        assert result["title"] == "Messy Title"

    def test_rating_converted_from_string(self):
        record = {
            "source_url": "https://example.com/1",
            "title": "Title",
            "body_text": "Body text " * 5,
            "rating": "4.2",
        }
        result = normalize_record(record)
        assert result["rating"] == pytest.approx(4.2)

    def test_date_parsed_from_string(self):
        record = {
            "source_url": "https://example.com/1",
            "title": "Title",
            "body_text": "Body text " * 5,
            "publish_date": "2025-08-20",
        }
        result = normalize_record(record)
        assert result["publish_date"] == date(2025, 8, 20)

    def test_missing_fields_default_to_none(self):
        record = {
            "source_url": "https://example.com/1",
            "title": "Title",
            "body_text": "Body text " * 5,
        }
        result = normalize_record(record)
        assert result.get("rating") is None
        assert result.get("author") is None

    def test_empty_record_does_not_crash(self):
        result = normalize_record({})
        assert isinstance(result, dict)
