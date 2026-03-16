"""
scrapers/competitor_pricing_scraper.py
---------------------------------------
Scraper for competitor insurance pricing comparison pages.

Architecture contract
---------------------
- ``run()``   — inherited from BaseScraper; fetches each URL in ``start_urls``
               and persists raw HTML to ``raw_pages`` (is_parsed=False).
- ``parse()`` — deprecated; implemented only to satisfy the abstract interface.
               Structured extraction from ``raw_pages`` is performed later by
               ``parsers.automotive_pipeline.ParserPipeline``.

Target data model: ``database.models.CompetitorPricing``
"""

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper


class CompetitorPricingScraper(BaseScraper):
    """Scraper for insurance price comparison pages.

    Seed URLs point to car-insurance quote/review pages on well-known
    comparison and review sites.  Raw HTML is stored in ``raw_pages``
    for downstream extraction by the parser pipeline.
    """

    source_name = "competitor_pricing"
    start_urls = [
        "https://www.comparethemarket.com/car-insurance/",
        "https://www.moneysupermarket.com/car-insurance/",
        "https://www.confused.com/car-insurance",
        "https://www.gocompare.com/car-insurance/",
        "https://www.insurancequotes.com/auto",
    ]
    rate_limit = 0.5  # conservative

    # ------------------------------------------------------------------
    # Deprecated parse() — implemented to satisfy abstract interface only.
    # This method is NOT called by BaseScraper.run().
    # ------------------------------------------------------------------

    def parse(self, html: str) -> list[dict]:
        """Extract pricing records from raw HTML.

        .. deprecated::
            Not called by ``run()``. Use ``ParserPipeline`` instead.
        """
        soup = BeautifulSoup(html, "html.parser")
        records = []

        # --- company / page title -----------------------------------------
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else ""

        company_name = "Unknown Insurer"
        for candidate in ["GEICO", "Allianz", "AXA", "Progressive",
                          "State Farm", "Allstate", "Admiral"]:
            if candidate.lower() in page_title.lower() or candidate.lower() in html.lower():
                company_name = candidate
                break

        # --- price --------------------------------------------------------
        price = None
        for pattern in [
            re.compile(r"[\$€£]\s*([\d,.]+)", re.I),
            re.compile(r"([\d,.]+)\s*(per\s+year|\/yr|\/month|\/mo)", re.I),
        ]:
            match = pattern.search(soup.get_text())
            if match:
                try:
                    price = float(match.group(1).replace(",", ""))
                    break
                except ValueError:
                    pass

        # --- coverage type ------------------------------------------------
        coverage_type = None
        for ctype in ["comprehensive", "third party", "third-party", "liability", "collision"]:
            if ctype in html.lower():
                coverage_type = ctype.title()
                break

        # --- region -------------------------------------------------------
        region = None
        region_meta = soup.find("meta", {"name": "geo.region"})
        if region_meta and region_meta.get("content"):
            region = region_meta["content"]

        records.append({
            "company_name": company_name,
            "price": price,
            "coverage_type": coverage_type,
            "region": region,
            "currency": "EUR",
            "snapshot_date": date.today(),
        })

        self.logger.info(
            "parse() produced %d pricing record(s) for company='%s'",
            len(records), company_name,
        )
        return records
