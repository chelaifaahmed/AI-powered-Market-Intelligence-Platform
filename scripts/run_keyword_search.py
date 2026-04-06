"""
scripts/run_keyword_search.py
------------------------------
Runs keyword-based article discovery for all active SearchKeyword entries.

Usage:
    python -m scripts.run_keyword_search
    python -m scripts.run_keyword_search --max-per-keyword 20
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.keyword_search")


def main():
    parser = argparse.ArgumentParser(description="Run keyword-based article discovery")
    parser.add_argument("--max-per-keyword", type=int, default=15,
                        help="Max articles to store per keyword (default: 15)")
    args = parser.parse_args()

    from scrapers.keyword_scraper import run_keyword_search

    logger.info("=" * 56)
    logger.info("Keyword Search starting")
    logger.info("=" * 56)

    metrics = run_keyword_search(max_articles_per_keyword=args.max_per_keyword)

    logger.info("=" * 56)
    logger.info("Keyword Search complete")
    logger.info("  Keywords searched  : %d", metrics["keywords_searched"])
    logger.info("  Articles found     : %d", metrics["articles_found"])
    logger.info("  Articles inserted  : %d", metrics["articles_inserted"])
    logger.info("  Duplicates skipped : %d", metrics["articles_duplicate"])
    logger.info("=" * 56)


if __name__ == "__main__":
    main()
