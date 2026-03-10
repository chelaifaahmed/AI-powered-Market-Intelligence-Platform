"""
scripts/test_scraper.py
-----------------------
Phase 3A — Demonstration script for the scraping infrastructure.

This script:
1. Defines a concrete BaseScraper subclass targeting 2 public automotive pages.
2. Fetches their HTML and stores each page in the ``raw_pages`` database table.
3. Prints the parsed page titles.
4. Queries ``SELECT COUNT(*) FROM raw_pages`` and prints the result.

Run from the project root:
    python scripts/test_scraper.py

Expected output:
    ... INFO | Fetching: https://www.caranddriver.com
    ... INFO | Stored raw_page for https://www.caranddriver.com
    ... INFO | Fetching: https://www.autotrader.com
    ... INFO | Stored raw_page for https://www.autotrader.com
    ✅ Parsed titles:
       [1] Car and Driver | Car Reviews, Buying Guides …
       [2] Used Cars for Sale, New Cars for Sale …
    ✅ raw_pages table now has N row(s).
"""

import re
import sys
import os

# ---------------------------------------------------------------------------
# Ensure project root is on the Python path when run as a script
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scrapers.base_scraper import BaseScraper


# ---------------------------------------------------------------------------
# Concrete scraper subclass
# ---------------------------------------------------------------------------

class AutomotiveDemoScraper(BaseScraper):
    """Minimal demo scraper that fetches the home pages of two automotive sites.

    It extracts only the HTML ``<title>`` tag to prove fetching + parsing work,
    while the raw HTML is persisted to ``raw_pages`` by the base class.
    """

    source_name = "automotive_demo"
    start_urls = [
        "https://www.caranddriver.com",
        "https://www.autotrader.com",
    ]
    rate_limit = 0.5   # 1 request every 2 seconds — polite crawling

    # Regex to extract <title> content (handles multi-line and attributes)
    _TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

    def parse(self, html: str) -> list[dict]:
        """Extract the page <title> as a minimal parsed record.

        Args:
            html (str): Raw HTML of the fetched page.

        Returns:
            list[dict]: Single-element list with {'title': <page title>}.
        """
        match = self._TITLE_RE.search(html)
        title = match.group(1).strip() if match else "(no title)"
        # Collapse whitespace / newlines inside title
        title = re.sub(r"\s+", " ", title)
        self.logger.debug("Extracted title: %s", title)
        return [{"title": title}]


# ---------------------------------------------------------------------------
# Verification helper — query raw_pages count
# ---------------------------------------------------------------------------

def get_raw_pages_count() -> int:
    """Return the total number of rows in the raw_pages table."""
    from database.connection import get_db_session
    from sqlalchemy import text

    with get_db_session() as session:
        result = session.execute(text("SELECT COUNT(*) FROM raw_pages"))
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Phase 3A  — Scraping Infrastructure Demo")
    print("=" * 60)
    print()

    # ── Run the scraper
    scraper = AutomotiveDemoScraper()
    results = scraper.run()

    # ── Print parsed titles
    print()
    print("✅  Parsed titles:")
    for idx, record in enumerate(results, start=1):
        print(f"   [{idx}] {record.get('title', '(empty)')}")

    # ── DB verification
    print()
    try:
        count = get_raw_pages_count()
        print(f"✅  raw_pages table now has {count} row(s).")
        if count >= 2:
            print("    Requirement satisfied: COUNT(*) >= 2 ✓")
        else:
            print("    ⚠️  COUNT(*) < 2 — check DB connection or errors above.")
    except Exception as exc:
        print(f"❌  Could not query raw_pages: {exc}")

    print()
    print("Done. Check logs/scraper.log for the full structured log.")
    print("=" * 60)


if __name__ == "__main__":
    main()
