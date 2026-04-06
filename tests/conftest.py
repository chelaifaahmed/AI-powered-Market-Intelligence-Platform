"""
tests/conftest.py
------------------
Shared pytest fixtures for the Automotive Market Intelligence Platform test suite.
"""

import os
import sys
from datetime import date
from unittest.mock import MagicMock

import pytest

# Ensure project root is importable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Golden record fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_car_review_record():
    """A fully valid normalized car review record."""
    return {
        "source_url": "https://www.caranddriver.com/toyota/camry/review",
        "title": "Toyota Camry Long-Term Review",
        "body_text": (
            "The Toyota Camry continues to be one of the best midsize sedans available. "
            "It offers excellent reliability, a smooth ride, and great fuel efficiency. "
            "The 2024 model adds improved infotainment and updated safety features."
        ),
        "author": "John Doe",
        "rating": 4.5,
        "publish_date": date(2025, 10, 1),
        "brand": "Toyota",
        "model": "Camry",
    }


@pytest.fixture
def valid_insurance_review_record():
    """A fully valid normalized insurance review record."""
    return {
        "source_url": "https://www.trustpilot.com/review/axa.com/1",
        "title": "AXA handled my claim professionally",
        "body_text": (
            "AXA insurance handled my claim very efficiently. "
            "The process was clear, the staff were helpful, "
            "and I received my settlement within two weeks. Highly recommended."
        ),
        "author": "Jane Smith",
        "rating": 4.8,
        "publish_date": date(2025, 11, 15),
        "brand": "AXA",
    }


@pytest.fixture
def minimal_valid_record():
    """Minimum fields needed to pass validation."""
    return {
        "source_url": "https://example.com/review/1",
        "title": "A decent review title",
        "body_text": "A" * 60,  # just above the 50-char minimum
    }


@pytest.fixture
def mock_session():
    """A MagicMock that mimics a SQLAlchemy Session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter_by.return_value.first.return_value = None
    return session
