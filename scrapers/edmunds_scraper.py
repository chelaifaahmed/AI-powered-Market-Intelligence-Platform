"""
scrapers/edmunds_scraper.py
-----------------------------
Playwright scraper for Edmunds (edmunds.com) consumer car reviews.

Edmunds has rich user reviews with ratings, pros/cons, and detailed text.
Target data model: CarReview
Entity type routed by parser: car_review
"""

from __future__ import annotations

from scrapers.playwright_base_scraper import PlaywrightBaseScraper


class EdmundsScraper(PlaywrightBaseScraper):
    """Scrapes consumer car reviews from Edmunds."""

    source_name = "edmunds"
    rate_limit = 0.25

    start_urls = [
        "https://www.edmunds.com/toyota/camry/review/",
        "https://www.edmunds.com/honda/civic/review/",
        "https://www.edmunds.com/bmw/3-series/review/",
        "https://www.edmunds.com/tesla/model-3/review/",
        "https://www.edmunds.com/ford/f-150/review/",
        "https://www.edmunds.com/chevrolet/equinox/review/",
        "https://www.edmunds.com/hyundai/elantra/review/",
        "https://www.edmunds.com/volkswagen/jetta/review/",
    ]

    def _after_navigate(self, page) -> None:
        """Scroll through reviews to trigger lazy loading."""
        try:
            # Accept cookies if banner appears
            for selector in [
                "#onetrust-accept-btn-handler",
                "button[aria-label='Accept All']",
                ".accept-cookies",
            ]:
                try:
                    page.click(selector, timeout=2000)
                    break
                except Exception:
                    pass

            # Scroll to load review content
            for _ in range(4):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(700)
        except Exception:
            pass

    def parse(self, html: str) -> list[dict]:
        """Deprecated — parsing handled by ParserPipeline."""
        return []
