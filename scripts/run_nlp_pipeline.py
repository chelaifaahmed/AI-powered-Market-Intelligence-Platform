"""
scripts/run_nlp_pipeline.py
----------------------------
NLP enrichment runner — processes unprocessed reviews and articles
through the NLP pipeline (sentiment, topics, keywords, complaints).

Usage:
    python scripts/run_nlp_pipeline.py              # default batch of 500
    python scripts/run_nlp_pipeline.py --limit 100  # custom batch size
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.run_nlp_pipeline")


def main(batch_limit: int = 500) -> dict:
    """Run NLP enrichment on all unprocessed records.

    Args:
        batch_limit: Max records to process per entity type per run.

    Returns:
        dict with per-type metrics.
    """
    from database.connection import get_db_session
    from nlp.nlp_pipeline import NlpPipeline
    from observability.step_recorder import StepRecorder, derive_step_status

    started = datetime.now(timezone.utc)
    separator = "=" * 56
    logger.info(separator)
    logger.info("NLP Pipeline run starting — %s UTC", started.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("batch_limit=%d", batch_limit)
    logger.info(separator)

    all_metrics: dict = {}

    def _record_nlp_step(session, step_name: str, m: dict) -> None:
        """Persist a PipelineStepRun for one NLP stage and commit it."""
        recorder = StepRecorder(session, step_name, batch_limit=batch_limit)
        recorder.start()
        recorder.finish(
            records_processed=m["records_processed"],
            records_skipped=m["records_skipped"],
            records_failed=m["records_failed"],
            records_inserted=m["records_processed"],
            error_count=m["records_failed"],
            status=derive_step_status(m["records_processed"], m["records_failed"]),
        )
        session.commit()

    try:
        with get_db_session() as session:
            pipeline = NlpPipeline(session=session)

            logger.info("── Processing car reviews…")
            car_metrics = pipeline.process_car_reviews(limit=batch_limit)
            all_metrics["car_reviews"] = car_metrics
            _record_nlp_step(session, "nlp_car_reviews", car_metrics)
            logger.info(
                "   car_reviews: processed=%d  failed=%d  skipped=%d  (%.1f s)",
                car_metrics["records_processed"],
                car_metrics["records_failed"],
                car_metrics["records_skipped"],
                car_metrics["processing_time_seconds"],
            )

            logger.info("── Processing insurance reviews…")
            ins_metrics = pipeline.process_insurance_reviews(limit=batch_limit)
            all_metrics["insurance_reviews"] = ins_metrics
            _record_nlp_step(session, "nlp_insurance_reviews", ins_metrics)
            logger.info(
                "   insurance_reviews: processed=%d  failed=%d  skipped=%d  (%.1f s)",
                ins_metrics["records_processed"],
                ins_metrics["records_failed"],
                ins_metrics["records_skipped"],
                ins_metrics["processing_time_seconds"],
            )

            logger.info("── Processing market articles…")
            art_metrics = pipeline.process_articles(limit=batch_limit)
            all_metrics["articles"] = art_metrics
            _record_nlp_step(session, "nlp_articles", art_metrics)
            logger.info(
                "   articles: processed=%d  failed=%d  skipped=%d  (%.1f s)",
                art_metrics["records_processed"],
                art_metrics["records_failed"],
                art_metrics["records_skipped"],
                art_metrics["processing_time_seconds"],
            )

    except Exception as exc:
        logger.exception("NLP pipeline run failed with an unhandled exception: %s", exc)
        sys.exit(1)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    total_processed = sum(m["records_processed"] for m in all_metrics.values())
    total_failed = sum(m["records_failed"] for m in all_metrics.values())

    logger.info(separator)
    logger.info("NLP Pipeline Run — Summary")
    logger.info(separator)
    logger.info("  Total records processed : %d", total_processed)
    logger.info("  Total records failed    : %d", total_failed)
    logger.info("  Wall-clock time         : %.2f s", elapsed)
    logger.info(separator)

    if total_processed == 0:
        logger.info("No unprocessed records found — nothing to do.")

    return all_metrics


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run NLP enrichment pipeline on unprocessed reviews and articles."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        metavar="N",
        help="Max records to process per entity type (default: 500).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(batch_limit=args.limit)
