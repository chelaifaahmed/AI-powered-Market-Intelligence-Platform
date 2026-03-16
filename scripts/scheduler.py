"""
scripts/scheduler.py
--------------------
Master pipeline scheduler.

Ties the entire data platform together into a sequential execution loop:

  Step 1 — Scraping       scripts/run_scraping_tasks.py
  Step 2 — Parsing        scripts/run_parser_pipeline.py
  Step 3 — NLP Enrichment scripts/run_nlp_pipeline.py
  Step 4 — Analytics      scripts/run_analytics.py

Each step is imported and called directly (no subprocess overhead).
Failures in one step are logged but do NOT abort subsequent steps,
so a partial run still produces useful output.

Usage:
    # Run the full pipeline once, then exit:
    python scripts/scheduler.py --once

    # Run repeatedly every 6 hours (default):
    python scripts/scheduler.py

    # Run repeatedly every 2 hours:
    python scripts/scheduler.py --interval-hours 2

    # Run the full pipeline once immediately, then every N hours:
    python scripts/scheduler.py --run-on-start --interval-hours 4
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Callable

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path regardless of CWD
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.scheduler")

# ---------------------------------------------------------------------------
# Lazy step imports  (deferred so import errors surface clearly at runtime)
# ---------------------------------------------------------------------------

def _run_scraping() -> None:
    """Step 1 — execute all QUEUED scraping tasks → raw_pages."""
    from scripts.run_scraping_tasks import main as scraping_main
    scraping_main()


def _run_parsing() -> None:
    """Step 2 — parse raw_pages (is_parsed=False) → domain tables."""
    from scripts.run_parser_pipeline import run_parser_pipeline
    run_parser_pipeline(batch_limit=500, enable_llm=False)


def _run_nlp() -> None:
    """Step 3 — NLP-enrich unprocessed domain records."""
    from scripts.run_nlp_pipeline import main as nlp_main
    nlp_main()


def _run_analytics() -> None:
    """Step 4 — aggregate KPIs into analytics tables."""
    from scripts.run_analytics import run_analytics
    run_analytics()


# Ordered sequence of (label, callable) pairs
PIPELINE_STEPS: list[tuple[str, Callable]] = [
    ("Scraping       [run_scraping_tasks]",    _run_scraping),
    ("Parsing        [run_parser_pipeline]",   _run_parsing),
    ("NLP Enrichment [run_nlp_pipeline]",      _run_nlp),
    ("Analytics      [run_analytics]",         _run_analytics),
]


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------

def run_pipeline_once() -> dict:
    """Execute all four pipeline steps in sequence.

    Returns:
        dict mapping step label → 'ok' | 'failed: <error>'
    """
    started = datetime.now(timezone.utc)
    separator = "=" * 64
    logger.info(separator)
    logger.info("Pipeline run starting — %s UTC", started.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(separator)

    results: dict[str, str] = {}

    for idx, (label, fn) in enumerate(PIPELINE_STEPS, start=1):
        step_start = datetime.now(timezone.utc)
        logger.info("── Step %d/%d: %s", idx, len(PIPELINE_STEPS), label)
        try:
            fn()
            elapsed = (datetime.now(timezone.utc) - step_start).total_seconds()
            logger.info("   ✓ Step %d finished in %.1f s", idx, elapsed)
            results[label] = "ok"
        except Exception as exc:
            elapsed = (datetime.now(timezone.utc) - step_start).total_seconds()
            logger.exception(
                "   ✗ Step %d FAILED after %.1f s — %s: %s",
                idx, elapsed, type(exc).__name__, exc,
            )
            results[label] = f"failed: {exc}"

    total_elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    ok_count = sum(1 for v in results.values() if v == "ok")
    fail_count = len(results) - ok_count

    logger.info(separator)
    logger.info(
        "Pipeline run complete — %d/%d steps succeeded in %.1f s total",
        ok_count, len(PIPELINE_STEPS), total_elapsed,
    )
    if fail_count:
        logger.warning("%d step(s) failed — check logs above for details.", fail_count)
    logger.info(separator)

    return results


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------

def run_scheduler(interval_hours: float, run_on_start: bool) -> None:
    """Run ``run_pipeline_once()`` on a fixed interval until interrupted.

    Args:
        interval_hours: Hours between successive pipeline runs.
        run_on_start:   If True, execute immediately before the first sleep.
    """
    interval_seconds = interval_hours * 3600
    logger.info(
        "Scheduler started — interval=%.1f h (%d s), run_on_start=%s",
        interval_hours, int(interval_seconds), run_on_start,
    )
    logger.info("Press Ctrl+C to stop.")

    if run_on_start:
        run_pipeline_once()

    while True:
        next_run = datetime.now(timezone.utc).timestamp() + interval_seconds
        next_str = datetime.fromtimestamp(next_run, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        logger.info("Next pipeline run scheduled at %s UTC", next_str)

        # Sleep in 60-second ticks so Ctrl-C is responsive
        remaining = interval_seconds
        while remaining > 0:
            try:
                time.sleep(min(60, remaining))
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user (KeyboardInterrupt).")
                return
            remaining -= 60

        run_pipeline_once()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Master scheduler — runs the full data pipeline on a fixed interval.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        default=False,
        help="Run the pipeline exactly once, then exit.",
    )
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=6.0,
        metavar="N",
        help="Hours between successive pipeline runs (ignored with --once).",
    )
    parser.add_argument(
        "--run-on-start",
        action="store_true",
        default=False,
        help="Execute immediately before entering the scheduler loop.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.once:
        results = run_pipeline_once()
        failed = [k for k, v in results.items() if v != "ok"]
        sys.exit(1 if failed else 0)
    else:
        run_scheduler(
            interval_hours=args.interval_hours,
            run_on_start=args.run_on_start,
        )
