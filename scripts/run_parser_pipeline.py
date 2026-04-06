"""
scripts/run_parser_pipeline.py
------------------------------
Parser-pipeline orchestrator.

Reads unparsed rows from ``raw_pages`` (is_parsed=False) in batches and
pushes them through ``ParserPipeline.process_batch()``, which handles:
  - HTML cleaning
  - DOM / schema / LLM extraction
  - Normalisation + validation
  - Deduplication
  - Persisting structured records to domain tables (car_reviews, etc.)
  - Marking each raw_page as parsed (is_parsed=True)

Usage:
    python scripts/run_parser_pipeline.py              # default batch of 500
    python scripts/run_parser_pipeline.py --limit 100  # custom batch size
    python scripts/run_parser_pipeline.py --llm        # enable LLM extraction
"""

from __future__ import annotations

import argparse
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
from observability.step_recorder import StepRecorder, derive_step_status
from parsers.automotive_pipeline import ParserPipeline

# ---------------------------------------------------------------------------
# Logging — mirrors the style used throughout the project
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.run_parser_pipeline")


def run_parser_pipeline(batch_limit: int = 500, enable_llm: bool = False) -> None:
    """Process one batch of unparsed raw_pages through the parser pipeline.

    Args:
        batch_limit: Maximum number of raw_pages to process in this run.
        enable_llm:  When True, the pipeline supplements extraction with the
                     LLM extractor for sparse pages.
    """
    logger.info(
        "Parser pipeline starting — batch_limit=%d, enable_llm=%s",
        batch_limit,
        enable_llm,
    )
    started = datetime.now(timezone.utc)

    metrics: dict = {}
    try:
        with get_db_session() as session:
            pipeline = ParserPipeline(session=session, enable_llm=enable_llm)

            # process_batch() creates a PipelineRun and commits internally,
            # so we use the imperative StepRecorder to record around it.
            recorder = StepRecorder(
                session, "parser",
                batch_limit=batch_limit, enable_llm=enable_llm,
            )
            recorder.start()
            metrics = pipeline.process_batch(limit=batch_limit)
            recorder.finish(
                records_seen=metrics.get("pages_processed", 0),
                records_processed=metrics.get("records_extracted", 0),
                records_skipped=metrics.get("duplicates_detected", 0),
                records_failed=metrics.get("records_rejected", 0),
                records_inserted=metrics.get("records_extracted", 0),
                error_count=metrics.get("records_rejected", 0),
                status=derive_step_status(
                    metrics.get("records_extracted", 0),
                    metrics.get("records_rejected", 0),
                    metrics.get("pages_processed", 0),
                ),
            )
            session.commit()

    except Exception as exc:
        logger.exception("Parser pipeline run failed with an unhandled exception: %s", exc)
        sys.exit(1)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    # ------------------------------------------------------------------
    # Summary report
    # ------------------------------------------------------------------
    separator = "=" * 56
    logger.info(separator)
    logger.info("Parser Pipeline Run — Summary")
    logger.info(separator)
    logger.info("  Pages processed   : %d", metrics.get("pages_processed", 0))
    logger.info("  Records extracted : %d", metrics.get("records_extracted", 0))
    logger.info("  Records rejected  : %d", metrics.get("records_rejected", 0))
    logger.info("  Duplicates skipped: %d", metrics.get("duplicates_detected", 0))
    logger.info(
        "  Processing time   : %.3f s (pipeline) / %.3f s (wall-clock)",
        metrics.get("processing_time_seconds", 0.0),
        elapsed,
    )
    logger.info(separator)

    if metrics.get("pages_processed", 0) == 0:
        logger.info("No unparsed raw_pages found — nothing to do.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the automotive parser pipeline against unparsed raw_pages."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        metavar="N",
        help="Maximum number of raw_pages to process per run (default: 500).",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        default=False,
        help="Enable the LLM extractor for sparse pages.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_parser_pipeline(batch_limit=args.limit, enable_llm=args.llm)
