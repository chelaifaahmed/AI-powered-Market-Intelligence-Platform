"""
scripts/run_scraping_tasks.py
-----------------------------
Orchestrates queued scraping tasks using ScrapingTask + ScrapingRun.

Flow:
1. Load pending tasks (status=QUEUED), ordered by priority then scheduled_at.
2. Dynamically import scraper class from task.scraper_class.
3. Create a ScrapingRun row (RUNNING) and mark task RUNNING.
4. Execute scraper.run(scrape_task_id=..., run_id=...).
5. Update run metrics and task status on success/failure.
6. Persist ScrapingError rows for failures.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from sqlalchemy import asc, or_

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from database.connection import get_db_session
from database.enums import RunStatus, TaskStatus
from database.models import ScrapingError, ScrapingRun, ScrapingTask
from scrapers.base_scraper import BaseScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("scripts.run_scraping_tasks")


def _load_scraper_class(class_path: str) -> type[BaseScraper]:
    """Load scraper class from fully-qualified import path."""
    if "." not in class_path:
        raise ValueError(f"Invalid scraper_class '{class_path}'. Expected module.ClassName")

    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    if not isinstance(cls, type) or not issubclass(cls, BaseScraper):
        raise TypeError(f"{class_path} is not a BaseScraper subclass")

    return cls


def _pending_task_ids(limit: int | None = None) -> List[str]:
    """Return pending task IDs sorted by priority and schedule."""
    now = datetime.now(timezone.utc)
    with get_db_session() as session:
        query = (
            session.query(ScrapingTask.id)
            .filter(ScrapingTask.status == TaskStatus.QUEUED)
            .filter(
                or_(
                    ScrapingTask.scheduled_at.is_(None),
                    ScrapingTask.scheduled_at <= now,
                )
            )
            .order_by(asc(ScrapingTask.priority), asc(ScrapingTask.scheduled_at))
        )
        if limit is not None:
            query = query.limit(limit)

        return [str(row[0]) for row in query.all()]


def _process_task(task_id: str) -> None:
    """Execute one scraping task and update control-plane tracking tables."""
    with get_db_session() as session:
        task = session.get(ScrapingTask, task_id)
        if task is None:
            logger.warning("Task %s no longer exists; skipping", task_id)
            return
        if task.status != TaskStatus.QUEUED:
            logger.info("Task %s status is %s (not QUEUED); skipping", task.task_name, task.status.value)
            return

        logger.info("Starting task: %s (%s)", task.task_name, task.id)

        run = ScrapingRun(
            task_id=task.id,
            started_at=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            pages_fetched=0,
            records_extracted=0,
            records_rejected=0,
            bytes_downloaded=0,
        )
        session.add(run)
        task.status = TaskStatus.RUNNING
        session.flush()
        run_id = run.id
        session.commit()

        logger.info("Run ID: %s", run_id)

        started_at = datetime.now(timezone.utc)

        try:
            scraper_cls = _load_scraper_class(task.scraper_class)
            scraper = scraper_cls()

            records = scraper.run(scrape_task_id=task.id, run_id=run_id)
            metrics = scraper.get_run_metrics()

            finished_at = datetime.now(timezone.utc)
            duration_seconds = (finished_at - started_at).total_seconds()

            run.status = RunStatus.SUCCESS
            run.finished_at = finished_at
            run.duration_seconds = Decimal(f"{duration_seconds:.2f}")
            run.pages_fetched = int(metrics.get("pages_fetched", 0))
            run.records_extracted = int(metrics.get("records_extracted", len(records)))
            run.records_rejected = 0
            run.bytes_downloaded = int(metrics.get("bytes_downloaded", 0))
            run.exit_message = "Task completed successfully"

            task.status = TaskStatus.COMPLETED

            logger.info("Fetched pages: %d", run.pages_fetched)
            logger.info("Extracted records: %d", run.records_extracted)
            logger.info("Task completed successfully: %s", task.task_name)
            session.commit()

        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            duration_seconds = (finished_at - started_at).total_seconds()
            stack_trace = traceback.format_exc()

            run.status = RunStatus.FAILED
            run.finished_at = finished_at
            run.duration_seconds = Decimal(f"{duration_seconds:.2f}")
            run.exit_message = str(exc)

            task.status = TaskStatus.FAILED
            task.retry_count = (task.retry_count or 0) + 1

            session.add(
                ScrapingError(
                    run_id=run.id,
                    task_id=task.id,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    stack_trace=stack_trace,
                    target_url=task.target_url_pattern,
                    is_retryable=task.retry_count < task.max_retries,
                    occurred_at=finished_at,
                )
            )

            logger.exception("Task failed: %s (%s)", task.task_name, task.id)
            session.commit()


def main(limit: int | None = None) -> None:
    task_ids = _pending_task_ids(limit=limit)

    if not task_ids:
        logger.info("No pending tasks found.")
        return

    logger.info("Found %d pending task(s)", len(task_ids))
    for task_id in task_ids:
        _process_task(task_id)


if __name__ == "__main__":
    main()
