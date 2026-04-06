"""
tests/test_deduplicator.py
---------------------------
Unit tests for parsers/deduplicator.py

Verifies hash stability, collision resistance, and deduplication logic.
"""

import pytest

from parsers.deduplicator import compute_content_hash


class TestComputeContentHash:
    """Tests for the SHA-256 content hash function."""

    def test_returns_string(self):
        result = compute_content_hash("Toyota", "Camry", "https://example.com/1")
        assert isinstance(result, str)

    def test_returns_64_char_hex(self):
        """SHA-256 hex digest is always 64 characters."""
        result = compute_content_hash("Toyota", "Camry", "https://example.com/1")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_inputs_same_hash(self):
        h1 = compute_content_hash("Toyota", "Camry", "https://example.com/1")
        h2 = compute_content_hash("Toyota", "Camry", "https://example.com/1")
        assert h1 == h2

    def test_different_url_different_hash(self):
        h1 = compute_content_hash("Toyota", "Camry", "https://example.com/1")
        h2 = compute_content_hash("Toyota", "Camry", "https://example.com/2")
        assert h1 != h2

    def test_different_brand_different_hash(self):
        h1 = compute_content_hash("Toyota", "Camry", "https://example.com/1")
        h2 = compute_content_hash("Honda", "Camry", "https://example.com/1")
        assert h1 != h2

    def test_different_model_different_hash(self):
        h1 = compute_content_hash("Toyota", "Camry", "https://example.com/1")
        h2 = compute_content_hash("Toyota", "Corolla", "https://example.com/1")
        assert h1 != h2

    def test_none_brand_does_not_crash(self):
        result = compute_content_hash(None, "Camry", "https://example.com/1")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_none_model_does_not_crash(self):
        result = compute_content_hash("Toyota", None, "https://example.com/1")
        assert isinstance(result, str)

    def test_all_none_brand_model_with_url(self):
        # url is required (str), only brand/model can be None
        result = compute_content_hash(None, None, "https://example.com/")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_is_deterministic_across_calls(self):
        """Hash must be stable across process restarts (no random seeds)."""
        results = {compute_content_hash("BMW", "3 Series", "https://example.com/x") for _ in range(5)}
        assert len(results) == 1

    def test_url_case_insensitive(self):
        """compute_content_hash lowercases all inputs — same hash regardless of case."""
        h1 = compute_content_hash("BMW", "3 Series", "https://example.com/Review")
        h2 = compute_content_hash("BMW", "3 Series", "https://example.com/review")
        assert h1 == h2
