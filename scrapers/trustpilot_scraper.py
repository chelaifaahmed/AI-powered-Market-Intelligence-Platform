"""
scrapers/trustpilot_scraper.py
--------------------------------
Playwright scraper for Trustpilot insurance company reviews.

Targets insurance companies (AXA, Allianz, Admiral, etc.) to collect
customer sentiment data on their claims process, pricing, and service.

Target data model: InsuranceReview
Entity type routed by parser: insurance_review
"""

from __future__ import annotations

from scrapers.playwright_base_scraper import PlaywrightBaseScraper


class TrustpilotInsuranceScraper(PlaywrightBaseScraper):
    """Scrapes customer insurance reviews from Trustpilot."""

    source_name = "trustpilot_insurance"
    rate_limit = 0.2   # Trustpilot is strict — 1 req / 5s + jitter

    start_urls = [
        # UK insurance companies on Trustpilot
        "https://www.trustpilot.com/review/admiral.com",
        "https://www.trustpilot.com/review/www.directline.com",
        "https://www.trustpilot.com/review/www.aviva.co.uk",
        "https://www.trustpilot.com/review/www.lv.com",
        "https://www.trustpilot.com/review/www.hastingsdirect.com",
        "https://www.trustpilot.com/review/www.churchill.com",
        # Global insurers
        "https://www.trustpilot.com/review/www.axa.co.uk",
        "https://www.trustpilot.com/review/allianz.co.uk",
    ]

    def _after_navigate(self, page) -> None:
        """Wait for review cards to render and scroll to load more."""
        try:
            # Wait for review cards to appear
            page.wait_for_selector("[data-service-review-card-paper]", timeout=8000)
        except Exception:
            pass

        try:
            # Scroll through the reviews section
            for _ in range(5):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(600)
        except Exception:
            pass

    def parse(self, html: str) -> list[dict]:
        """Deprecated — parsing handled by ParserPipeline."""
        return []
