"""
scrapers/car_listing_scraper.py
--------------------------------
Scraper for car marketplace listings (e.g. AutoScout24).

Architecture contract
---------------------
- ``run()``   — inherited from BaseScraper; fetches each URL in ``start_urls``
               and persists raw HTML to ``raw_pages`` (is_parsed=False).
- ``parse()`` — deprecated; implemented only to satisfy the abstract interface.
               Structured extraction from ``raw_pages`` is performed later by
               ``parsers.automotive_pipeline.ParserPipeline``.

Target data model: ``database.models.CarListing``
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper


class CarListingScraper(BaseScraper):
    """Scraper for car marketplace listing pages.

    Seed URLs point to make/model search result pages on AutoScout24.
    Each fetched page contains multiple individual listings whose raw HTML
    is stored in ``raw_pages`` and later extracted by the parser pipeline.
    """

    source_name = "car_listings"
    start_urls = [
        "https://www.autoscout24.com/lst/toyota/camry",
        "https://www.autoscout24.com/lst/honda/accord",
        "https://www.autoscout24.com/lst/ford/f-150",
        "https://www.autoscout24.com/lst/tesla/model-3",
        "https://www.autoscout24.com/lst/volkswagen/golf",
    ]
    rate_limit = 0.5  # conservative; marketplace sites rate-limit aggressively

    # ------------------------------------------------------------------
    # Deprecated parse() — implemented to satisfy abstract interface only.
    # This method is NOT called by BaseScraper.run().
    # ------------------------------------------------------------------

    def parse(self, html: str) -> list[dict]:
        """Extract listing records from raw HTML.

        .. deprecated::
            Not called by ``run()``. Use ``ParserPipeline`` instead.
        """
        soup = BeautifulSoup(html, "html.parser")
        records = []

        # --- title / model -----------------------------------------------
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "Unknown Listing"

        # Naive brand/model inference from page title
        brand, model = "Unknown Brand", "Unknown Model"
        for known in [("Toyota", "Camry"), ("Honda", "Accord"),
                      ("Ford", "F-150"), ("Tesla", "Model 3"),
                      ("Volkswagen", "Golf")]:
            if known[0].lower() in title.lower():
                brand, model = known
                break

        # --- price --------------------------------------------------------
        listed_price = None
        price_tag = soup.find(class_=re.compile(r"price|amount", re.I))
        if price_tag:
            match = re.search(r"[\d\s,.]+", price_tag.get_text(strip=True).replace(" ", ""))
            if match:
                try:
                    listed_price = float(match.group().replace(",", "").replace(".", "").strip())
                except ValueError:
                    pass

        # --- mileage ------------------------------------------------------
        mileage_km = None
        km_tag = soup.find(string=re.compile(r"\d[\d\s,.]*\s*(km|miles)", re.I))
        if km_tag:
            match = re.search(r"([\d\s,.]+)\s*(km|miles)", km_tag, re.I)
            if match:
                try:
                    km_str = match.group(1).replace(" ", "").replace(",", "").replace(".", "")
                    mileage_km = int(km_str)
                    if "miles" in match.group(2).lower():
                        mileage_km = int(mileage_km * 1.60934)
                except ValueError:
                    pass

        # --- dealer / location --------------------------------------------
        dealer_name = None
        dealer_tag = soup.find(class_=re.compile(r"dealer|seller|vendor", re.I))
        if dealer_tag:
            dealer_name = dealer_tag.get_text(strip=True)[:200]

        # --- listed date --------------------------------------------------
        listed_at = None
        date_meta = soup.find("meta", {"property": "article:published_time"})
        if date_meta and date_meta.get("content"):
            try:
                listed_at = datetime.fromisoformat(
                    date_meta["content"].replace("Z", "+00:00")
                ).date()
            except ValueError:
                pass

        records.append({
            "listing_title": title,
            "brand": brand,
            "model": model,
            "listed_price": listed_price,
            "mileage_km": mileage_km,
            "dealer_name": dealer_name,
            "listed_at": listed_at,
            "currency": "EUR",
        })

        self.logger.info("parse() produced %d listing record(s) for '%s'", len(records), title)
        return records
