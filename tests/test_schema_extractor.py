"""
tests/test_schema_extractor.py
--------------------------------
Unit tests for parsers/schema_extractor.py

Tests entity type routing (the most critical business logic in the parser)
and JSON-LD extraction from HTML.
"""

import pytest

from parsers.schema_extractor import extract_from_schema, map_to_schema


class TestMapToSchema:
    """Tests for entity type routing in map_to_schema()."""

    # ------------------------------------------------------------------
    # car_listing routing
    # ------------------------------------------------------------------

    def test_autoscout24_url_routes_to_car_listing(self):
        result = map_to_schema({}, [], "https://www.autoscout24.com/lst/toyota/camry")
        assert result["entity_type"] == "car_listing"

    def test_autotrader_url_routes_to_car_listing(self):
        result = map_to_schema({}, [], "https://www.autotrader.com/cars-for-sale/used-cars")
        assert result["entity_type"] == "car_listing"

    def test_lst_path_routes_to_car_listing(self):
        result = map_to_schema({}, [], "https://www.somesite.com/lst/bmw/golf")
        assert result["entity_type"] == "car_listing"

    # ------------------------------------------------------------------
    # competitor_pricing routing
    # ------------------------------------------------------------------

    def test_comparethemarket_routes_to_pricing(self):
        result = map_to_schema({}, [], "https://www.comparethemarket.com/car-insurance/")
        assert result["entity_type"] == "competitor_pricing"

    def test_moneysupermarket_routes_to_pricing(self):
        result = map_to_schema({}, [], "https://www.moneysupermarket.com/car-insurance/")
        assert result["entity_type"] == "competitor_pricing"

    def test_confused_routes_to_pricing(self):
        result = map_to_schema({}, [], "https://www.confused.com/car-insurance")
        assert result["entity_type"] == "competitor_pricing"

    # ------------------------------------------------------------------
    # market_trend_article routing
    # ------------------------------------------------------------------

    def test_reuters_url_routes_to_article(self):
        result = map_to_schema({}, [], "https://www.reuters.com/business/autos/")
        assert result["entity_type"] == "market_trend_article"

    def test_news_title_routes_to_article(self):
        result = map_to_schema({"title": "Automotive market trends 2025"}, [], "https://unknown.com/page")
        assert result["entity_type"] == "market_trend_article"

    # ------------------------------------------------------------------
    # insurance_review routing
    # ------------------------------------------------------------------

    def test_insurance_url_routes_to_insurance_review(self):
        result = map_to_schema({}, [], "https://www.nerdwallet.com/car-insurance/")
        assert result["entity_type"] == "insurance_review"

    def test_insurance_title_routes_to_insurance_review(self):
        result = map_to_schema({"title": "Best car insurance policies 2025"}, [], "https://example.com/")
        assert result["entity_type"] == "insurance_review"

    # ------------------------------------------------------------------
    # car_review default
    # ------------------------------------------------------------------

    def test_unknown_url_defaults_to_car_review(self):
        result = map_to_schema({}, [], "https://www.someunknownsite.com/random")
        assert result["entity_type"] == "car_review"

    def test_caranddriver_defaults_to_car_review(self):
        result = map_to_schema({}, [], "https://www.caranddriver.com/toyota/camry")
        assert result["entity_type"] == "car_review"

    # ------------------------------------------------------------------
    # Priority order (listing > pricing > article > insurance > car)
    # ------------------------------------------------------------------

    def test_listing_beats_insurance_when_both_match(self):
        """A URL that could match both listing and insurance → listing wins."""
        result = map_to_schema(
            {"title": "car insurance listing"},
            [],
            "https://www.autoscout24.com/lst/toyota/camry",
        )
        assert result["entity_type"] == "car_listing"

    # ------------------------------------------------------------------
    # Record field mapping
    # ------------------------------------------------------------------

    def test_record_contains_source_url(self):
        url = "https://www.caranddriver.com/toyota/camry"
        result = map_to_schema({"title": "Review"}, [], url)
        assert result["record"]["source_url"] == url

    def test_record_maps_dom_fields(self):
        dom = {
            "title": "Toyota Camry Review",
            "body_text": "Great car.",
            "rating": 4.5,
            "brand": "Toyota",
            "model": "Camry",
        }
        result = map_to_schema(dom, [], "https://example.com/review")
        rec = result["record"]
        assert rec["title"] == "Toyota Camry Review"
        assert rec["rating"] == 4.5
        assert rec["brand"] == "Toyota"

    def test_listing_price_field_included(self):
        dom = {"listing_price": 24500.0}
        result = map_to_schema(dom, [], "https://www.autoscout24.com/lst/ford/f-150")
        assert "listing_price" in result["record"]
        assert result["record"]["listing_price"] == 24500.0


class TestExtractFromSchema:
    """Tests for JSON-LD extraction from HTML."""

    def test_returns_list(self):
        result = extract_from_schema("<html><body></body></html>")
        assert isinstance(result, list)

    def test_empty_html_returns_empty(self):
        assert extract_from_schema("") == []

    def test_extracts_single_entity(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Review", "name": "Test Review"}
        </script>
        </head></html>
        """
        result = extract_from_schema(html)
        assert len(result) >= 1
        assert any(e.get("@type") == "Review" for e in result)

    def test_extracts_product_entity(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Toyota Camry", "offers": {"@type": "Offer", "price": "25000"}}
        </script>
        </head></html>
        """
        result = extract_from_schema(html)
        types = {e.get("@type") for e in result}
        assert "Product" in types or "Offer" in types

    def test_invalid_json_ld_returns_empty(self):
        html = """
        <script type="application/ld+json">NOT VALID JSON {{{</script>
        """
        result = extract_from_schema(html)
        assert result == []

    def test_no_json_ld_returns_empty(self):
        html = "<html><head><title>No JSON-LD here</title></head><body>Content</body></html>"
        result = extract_from_schema(html)
        assert result == []
