"""
tests/test_parser_pipeline.py
------------------------------
Unit tests for parsers/automotive_pipeline.py

Tests the ParserPipeline.process_raw_page() logic using lightweight HTML
fixtures and a mocked SQLAlchemy session — no real DB required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from parsers.automotive_pipeline import ParserPipeline, AutomotivePipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_page(html, url):
    """Return a lightweight mock that looks like a RawPage without needing a DB session."""
    page = MagicMock()
    page.id = 1
    page.raw_html = html
    page.source_url = url
    page.is_parsed = False
    page.parse_error = None
    page.scrape_task_id = None
    return page


_CAR_REVIEW_HTML = """
<html>
<head>
  <title>Toyota Camry Review</title>
  <script type="application/ld+json">
  {"@type": "Review", "name": "Toyota Camry Review"}
  </script>
</head>
<body>
  <h1>Toyota Camry Review</h1>
  <p>
    The Toyota Camry is an excellent midsize sedan. It delivers outstanding reliability,
    smooth handling, impressive fuel economy, and a comfortable cabin that makes every
    drive enjoyable for commuters and families alike. Highly recommended.
  </p>
  <span class="rating">4.5</span>
</body>
</html>
"""

_CAR_LISTING_HTML = """
<html>
<head><title>2024 Toyota Camry for sale</title></head>
<body>
  <h1>2024 Toyota Camry</h1>
  <p>Price: $24,500</p>
</body>
</html>
"""

_INSURANCE_HTML = """
<html>
<head><title>Best car insurance policies 2025</title></head>
<body>
  <p>
    AXA car insurance offers comprehensive cover at competitive prices. Their claims
    process is fast and hassle-free. Customer service is excellent and response times
    are well within the industry benchmark. Highly recommend for new drivers.
  </p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter_by.return_value.first.return_value = None
    session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    # _get_or_create_* helpers call session.query(...).filter_by(...).first() → None
    # then session.add() + session.flush() → both are mocks (no-op)
    mock_obj = MagicMock()
    mock_obj.id = 999
    session.query.return_value.filter_by.return_value.first.return_value = None
    session.add.return_value = None
    session.flush.return_value = None
    return session


@pytest.fixture
def pipeline(mock_session):
    return ParserPipeline(session=mock_session, enable_llm=False)


# ---------------------------------------------------------------------------
# Empty / missing HTML
# ---------------------------------------------------------------------------

class TestEmptyHtml:
    def test_empty_html_is_rejected(self, pipeline):
        page = _make_raw_page("", "https://example.com/")
        result = pipeline.process_raw_page(page)
        assert result["status"] == "rejected"
        assert "empty" in result["reason"].lower()

    def test_none_html_is_rejected(self, pipeline):
        page = _make_raw_page(None, "https://example.com/")
        result = pipeline.process_raw_page(page)
        assert result["status"] == "rejected"

    def test_empty_html_marks_page_parsed(self, pipeline):
        page = _make_raw_page("", "https://example.com/")
        pipeline.process_raw_page(page)
        assert page.is_parsed is True


# ---------------------------------------------------------------------------
# Entity type routing (end-to-end through the pipeline stages)
# ---------------------------------------------------------------------------

class TestEntityTypeRouting:
    def test_car_listing_url_routes_correctly(self, pipeline):
        page = _make_raw_page(_CAR_LISTING_HTML, "https://www.autoscout24.com/lst/toyota/camry")
        result = pipeline.process_raw_page(page)
        # Listing may pass or fail validation but entity_type should be car_listing
        assert result.get("entity_type") == "car_listing"

    def test_insurance_url_routes_correctly(self, pipeline):
        page = _make_raw_page(_INSURANCE_HTML, "https://example.com/")
        result = pipeline.process_raw_page(page)
        # title triggers insurance_review routing
        assert result.get("entity_type") == "insurance_review"

    def test_car_review_is_default_entity(self, pipeline):
        page = _make_raw_page(_CAR_REVIEW_HTML, "https://www.caranddriver.com/toyota/camry")
        result = pipeline.process_raw_page(page)
        assert result.get("entity_type") == "car_review"


# ---------------------------------------------------------------------------
# Result status shape
# ---------------------------------------------------------------------------

class TestResultShape:
    def test_result_always_has_status_key(self, pipeline):
        page = _make_raw_page(_CAR_REVIEW_HTML, "https://www.caranddriver.com/toyota/camry")
        result = pipeline.process_raw_page(page)
        assert "status" in result

    def test_status_is_valid_value(self, pipeline):
        page = _make_raw_page(_CAR_REVIEW_HTML, "https://www.caranddriver.com/toyota/camry")
        result = pipeline.process_raw_page(page)
        assert result["status"] in {"stored", "rejected", "duplicate"}

    def test_rejected_result_has_reason(self, pipeline):
        page = _make_raw_page("", "https://example.com/")
        result = pipeline.process_raw_page(page)
        assert "reason" in result

    def test_page_is_marked_parsed_on_success(self, pipeline):
        page = _make_raw_page(_CAR_REVIEW_HTML, "https://www.caranddriver.com/toyota/camry")
        pipeline.process_raw_page(page)
        assert page.is_parsed is True


# ---------------------------------------------------------------------------
# process_page() convenience wrapper
# ---------------------------------------------------------------------------

class TestProcessPage:
    def test_process_page_returns_dict(self, pipeline):
        result = pipeline.process_page(_CAR_REVIEW_HTML, "https://www.caranddriver.com/toyota/camry")
        assert isinstance(result, dict)
        assert "status" in result

    def test_process_page_empty_html(self, pipeline):
        result = pipeline.process_page("", "https://example.com/")
        assert result["status"] == "rejected"


# ---------------------------------------------------------------------------
# AutomotivePipeline backward-compat alias
# ---------------------------------------------------------------------------

class TestAutomotivePipelineAlias:
    def test_automotive_pipeline_is_subclass(self, mock_session):
        ap = AutomotivePipeline(session=mock_session)
        assert isinstance(ap, ParserPipeline)

    def test_automotive_pipeline_process_page_delegates(self, mock_session):
        ap = AutomotivePipeline(session=mock_session)
        result = ap.process_page(_CAR_REVIEW_HTML, "https://www.caranddriver.com/toyota/camry")
        assert isinstance(result, dict)
        assert "status" in result
