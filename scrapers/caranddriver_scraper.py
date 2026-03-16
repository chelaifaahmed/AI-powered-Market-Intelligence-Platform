"""
scrapers/caranddriver_scraper.py
----------------------------------
Playwright scraper for Car and Driver (caranddriver.com) expert car reviews.

Target data model: CarReview
Entity type routed by parser: car_review
"""

from __future__ import annotations

from scrapers.playwright_base_scraper import PlaywrightBaseScraper


class CarAndDriverScraper(PlaywrightBaseScraper):
    """Scrapes expert and long-term car reviews from Car and Driver."""

    source_name = "caranddriver"
    rate_limit = 0.25   # 1 request per 4 seconds + random jitter

    start_urls = [
        "https://www.caranddriver.com/toyota/camry",
        "https://www.caranddriver.com/honda/civic",
        "https://www.caranddriver.com/bmw/3-series",
        "https://www.caranddriver.com/tesla/model-3",
        "https://www.caranddriver.com/ford/f-150",
        "https://www.caranddriver.com/volkswagen/golf",
        "https://www.caranddriver.com/toyota/corolla",
        "https://www.caranddriver.com/hyundai/tucson",
    ]

    def _after_navigate(self, page) -> None:
        """Scroll to reveal lazy-loaded review content."""
        try:
            # Dismiss cookie/privacy banner if present
            for selector in ["button[data-testid='accept']", "#onetrust-accept-btn-handler", ".close-button"]:
                try:
                    page.click(selector, timeout=2000)
                    break
                except Exception:
                    pass
            # Scroll down to load all content
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(800)
        except Exception:
            pass

    def parse(self, html: str) -> list[dict]:
        """Deprecated — parsing handled by ParserPipeline."""
        return []
