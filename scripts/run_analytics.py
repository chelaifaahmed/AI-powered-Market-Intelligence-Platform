"""
scripts/run_analytics.py
------------------------
Analytics orchestrator.

Executes all aggregation functions defined in ``analytics/aggregators.py``
against the live database and logs a summary of the results.

Aggregations run:
  1. compute_brand_reputation  — monthly brand KPIs → brand_reputation_scores
                                                     + sentiment_trends

Usage:
    python scripts/run_analytics.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path regardless of CWD
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from database.connection import get_db_session
from analytics.aggregators import compute_brand_reputation

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.run_analytics")


def run_analytics() -> None:
    """Execute all analytics aggregations and commit results."""
    logger.info("Analytics run starting …")
    started = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # 1. Brand Reputation & Sentiment Trends
    # ------------------------------------------------------------------
    try:
        with get_db_session() as session:
            rep_metrics = compute_brand_reputation(session)
    except Exception as exc:
        logger.exception("compute_brand_reputation failed: %s", exc)
        sys.exit(1)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    # ------------------------------------------------------------------
    # Summary report
    # ------------------------------------------------------------------
    separator = "=" * 60
    logger.info(separator)
    logger.info("Analytics Run — Summary")
    logger.info(separator)
    logger.info("compute_brand_reputation:")
    logger.info(
        "  (brand, month) groups found   : %d",
        rep_metrics.get("brand_periods_found", 0),
    )
    logger.info(
        "  BrandReputationScore inserted : %d",
        rep_metrics.get("reputation_inserted", 0),
    )
    logger.info(
        "  BrandReputationScore updated  : %d",
        rep_metrics.get("reputation_updated", 0),
    )
    logger.info(
        "  SentimentTrend inserted       : %d",
        rep_metrics.get("trend_inserted", 0),
    )
    logger.info(
        "  SentimentTrend updated        : %d",
        rep_metrics.get("trend_updated", 0),
    )
    logger.info("Wall-clock time: %.3f s", elapsed)
    logger.info(separator)

    if rep_metrics.get("brand_periods_found", 0) == 0:
        logger.warning(
            "No data found. Ensure car_reviews with review_date are present "
            "and the NLP pipeline has run (car_review_nlp rows expected)."
        )


if __name__ == "__main__":
    run_analytics()
