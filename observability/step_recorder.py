"""
observability/step_recorder.py
-------------------------------
Lightweight helpers for recording PipelineStepRun rows.

Usage — context manager (preferred):

    with record_step(session, "parser", batch_limit=500) as step:
        metrics = pipeline.process_batch(limit=500)
        step.records_seen      = metrics["pages_processed"]
        step.records_processed = metrics["records_extracted"]
        step.records_skipped   = metrics["duplicates_detected"]
        step.records_failed    = metrics["records_rejected"]
        step.records_inserted  = metrics["records_extracted"]
        step.status = _derive_status(metrics)
    # step row is flushed on exit; caller is responsible for commit.

Usage — imperative (for wrapping code that commits internally):

    recorder = StepRecorder(session, "nlp_car_reviews", batch_limit=100)
    recorder.start()
    metrics = pipeline.process_car_reviews(limit=100)   # commits inside
    recorder.finish(
        records_processed=metrics["records_processed"],
        records_skipped=metrics["records_skipped"],
        records_failed=metrics["records_failed"],
        records_inserted=metrics["records_processed"],
        error_count=metrics["records_failed"],
    )
    session.commit()

IMPORTANT: Both helpers call session.flush() internally but do NOT commit.
The caller decides when to commit.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from database.enums import PipelineStatus
from database.models import PipelineStepRun

logger = logging.getLogger("observability.step_recorder")


# ---------------------------------------------------------------------------
# Status helper
# ---------------------------------------------------------------------------

def derive_step_status(
    records_processed: int,
    records_failed: int,
    records_seen: int = 0,
) -> PipelineStatus:
    """
    Derive a PipelineStatus from processed/failed counts.

    Rules:
    - No records seen at all → SUCCESS (nothing to do is fine)
    - All failed and nothing processed → FAILED
    - Some failed but some processed → PARTIAL
    - No failures → SUCCESS
    """
    if records_failed == 0:
        return PipelineStatus.SUCCESS
    if records_processed == 0:
        return PipelineStatus.FAILED
    return PipelineStatus.PARTIAL


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

@contextmanager
def record_step(
    session: Session,
    step_name: str,
    pipeline_run_id: Optional[UUID] = None,
    **metadata: Any,
) -> Generator[PipelineStepRun, None, None]:
    """
    Context manager that creates a PipelineStepRun, yields it for the caller
    to populate, then closes the step with timing and a flush.

    Does NOT commit — the caller owns the transaction boundary.

    Raises:
        Re-raises any exception from the body after marking the step FAILED.
    """
    step = PipelineStepRun(
        step_name=step_name,
        pipeline_run_id=pipeline_run_id,
        status=PipelineStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
        step_metadata=dict(metadata) if metadata else None,
    )
    session.add(step)
    session.flush()

    try:
        yield step
        # Auto-close if still RUNNING (caller may have already set status)
        if step.status == PipelineStatus.RUNNING:
            step.status = PipelineStatus.SUCCESS
    except Exception:
        step.status = PipelineStatus.FAILED
        step.error_count = (step.error_count or 0) + 1
        raise
    finally:
        step.finished_at = datetime.now(timezone.utc)
        if step.started_at and step.finished_at:
            delta = (step.finished_at - step.started_at).total_seconds()
            step.duration_ms = int(delta * 1000)
        session.flush()
        logger.debug(
            "Step %r finished — status=%s processed=%d failed=%d duration_ms=%s",
            step.step_name,
            step.status.value if step.status else "?",
            step.records_processed,
            step.records_failed,
            step.duration_ms,
        )


# ---------------------------------------------------------------------------
# Imperative class — for steps that commit internally (e.g. process_batch)
# ---------------------------------------------------------------------------

class StepRecorder:
    """
    Imperative step recorder for pipeline stages that call session.commit()
    internally, making it unsafe to use the context manager across the call.

    Pattern:
        recorder = StepRecorder(session, "parser")
        recorder.start()
        metrics = pipeline.process_batch(limit=500)   # may commit inside
        recorder.finish(**_map_metrics(metrics))
        session.commit()
    """

    def __init__(
        self,
        session: Session,
        step_name: str,
        pipeline_run_id: Optional[UUID] = None,
        **metadata: Any,
    ) -> None:
        self.session = session
        self.step_name = step_name
        self.pipeline_run_id = pipeline_run_id
        self.metadata = dict(metadata) if metadata else None
        self._step: Optional[PipelineStepRun] = None
        self._started_at: Optional[datetime] = None

    def start(self) -> "StepRecorder":
        """Insert the step row (RUNNING) and flush."""
        self._started_at = datetime.now(timezone.utc)
        self._step = PipelineStepRun(
            step_name=self.step_name,
            pipeline_run_id=self.pipeline_run_id,
            status=PipelineStatus.RUNNING,
            started_at=self._started_at,
            step_metadata=self.metadata,
        )
        self.session.add(self._step)
        self.session.flush()
        return self

    def finish(
        self,
        records_seen: int = 0,
        records_processed: int = 0,
        records_skipped: int = 0,
        records_failed: int = 0,
        records_inserted: int = 0,
        error_count: int = 0,
        status: Optional[PipelineStatus] = None,
    ) -> PipelineStepRun:
        """Update the step row with final metrics and flush."""
        if self._step is None:
            raise RuntimeError("StepRecorder.finish() called before start()")

        finished_at = datetime.now(timezone.utc)
        self._step.finished_at = finished_at
        self._step.duration_ms = int(
            (finished_at - (self._started_at or finished_at)).total_seconds() * 1000
        )
        self._step.records_seen = records_seen
        self._step.records_processed = records_processed
        self._step.records_skipped = records_skipped
        self._step.records_failed = records_failed
        self._step.records_inserted = records_inserted
        self._step.error_count = error_count
        self._step.status = status or derive_step_status(records_processed, records_failed, records_seen)

        self.session.flush()
        logger.debug(
            "Step %r finished — status=%s processed=%d failed=%d duration_ms=%d",
            self.step_name,
            self._step.status.value if self._step.status else "?",
            records_processed,
            records_failed,
            self._step.duration_ms or 0,
        )
        return self._step
