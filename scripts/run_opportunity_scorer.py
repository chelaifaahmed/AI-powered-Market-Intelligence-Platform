"""
scripts/run_opportunity_scorer.py
----------------------------------
Opportunity scoring orchestrator.

Executes ``analytics.opportunity_scorer.compute_opportunity_signals()``
against the live database, records a PipelineStepRun, and logs a summary.

Usage:
    python scripts/run_opportunity_scorer.py
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

from analytics.opportunity_scorer import compute_opportunity_signals
from database.connection import get_db_session
from observability.step_recorder import StepRecorder, derive_step_status

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.run_opportunity_scorer")


def run_opportunity_scorer() -> None:
    """Execute opportunity scoring and commit results."""
    logger.info("Opportunity scoring run starting ...")
    started = datetime.now(timezone.utc)

    try:
        with get_db_session() as session:
            recorder = StepRecorder(session, "opportunity_scorer", component="compute_opportunity_signals")
            recorder.start()
            signals = compute_opportunity_signals(session)

            strong = sum(1 for s in signals if s["signal_strength"] == "strong")
            moderate = sum(1 for s in signals if s["signal_strength"] == "moderate")
            weak = sum(1 for s in signals if s["signal_strength"] == "weak")

            recorder.finish(
                records_seen=len(signals),
                records_processed=len(signals),
                records_inserted=len(signals),
                status=derive_step_status(
                    records_processed=len(signals),
                    records_failed=0,
                ),
            )
            session.commit()
    except Exception as exc:
        logger.exception("compute_opportunity_signals failed: %s", exc)
        sys.exit(1)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    # ------------------------------------------------------------------
    # Summary report
    # ------------------------------------------------------------------
    separator = "=" * 60
    logger.info(separator)
    logger.info("Opportunity Scoring Run - Summary")
    logger.info(separator)
    logger.info("  Total signals computed : %d", len(signals))
    logger.info("  Strong signals         : %d", strong)
    logger.info("  Moderate signals       : %d", moderate)
    logger.info("  Weak signals           : %d", weak)
    logger.info("  Wall-clock time        : %.3f s", elapsed)
    logger.info(separator)

    if signals:
        top = max(signals, key=lambda s: s["overall_score"])
        logger.info(
            "  Top opportunity: %s (%s) — score %.1f [%s]",
            top["entity_name"], top["entity_type"],
            top["overall_score"], top["signal_strength"],
        )
        logger.info(separator)


if __name__ == "__main__":
    run_opportunity_scorer()
