"""
tests/test_observability.py
----------------------------
Unit tests for observability/step_recorder.py

Covers:
- derive_step_status() logic
- StepRecorder imperative API
- record_step() context manager
- Metric propagation (records_seen, processed, failed, inserted)
- Status transitions (success, partial, failed)
- Exception handling in context manager
- flush/session interaction
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from database.enums import PipelineStatus
from database.models import PipelineStepRun
from observability.step_recorder import (
    StepRecorder,
    derive_step_status,
    record_step,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    """Return a MagicMock session that captures add/flush/commit calls."""
    session = MagicMock()
    session.add.return_value = None
    session.flush.return_value = None
    session.commit.return_value = None
    return session


# ---------------------------------------------------------------------------
# derive_step_status
# ---------------------------------------------------------------------------

class TestDeriveStepStatus:
    def test_no_failures_returns_success(self):
        assert derive_step_status(100, 0) == PipelineStatus.SUCCESS

    def test_zero_processed_zero_failed_returns_success(self):
        # Nothing to do — still success
        assert derive_step_status(0, 0) == PipelineStatus.SUCCESS

    def test_all_failed_none_processed_returns_failed(self):
        assert derive_step_status(0, 10) == PipelineStatus.FAILED

    def test_some_failed_some_processed_returns_partial(self):
        assert derive_step_status(8, 2) == PipelineStatus.PARTIAL

    def test_single_failure_with_many_processed_is_partial(self):
        assert derive_step_status(99, 1) == PipelineStatus.PARTIAL


# ---------------------------------------------------------------------------
# StepRecorder — imperative API
# ---------------------------------------------------------------------------

class TestStepRecorder:
    def test_start_adds_step_to_session(self):
        session = _make_session()
        recorder = StepRecorder(session, "parser")
        recorder.start()
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert isinstance(added, PipelineStepRun)
        assert added.step_name == "parser"
        assert added.status == PipelineStatus.RUNNING

    def test_start_flushes(self):
        session = _make_session()
        recorder = StepRecorder(session, "nlp_car_reviews")
        recorder.start()
        session.flush.assert_called()

    def test_finish_without_start_raises(self):
        session = _make_session()
        recorder = StepRecorder(session, "parser")
        with pytest.raises(RuntimeError, match="start"):
            recorder.finish()

    def test_finish_sets_metrics(self):
        session = _make_session()
        recorder = StepRecorder(session, "parser")
        recorder.start()
        step = recorder.finish(
            records_seen=100,
            records_processed=90,
            records_skipped=5,
            records_failed=5,
            records_inserted=90,
            error_count=5,
        )
        assert step.records_seen == 100
        assert step.records_processed == 90
        assert step.records_skipped == 5
        assert step.records_failed == 5
        assert step.records_inserted == 90
        assert step.error_count == 5

    def test_finish_sets_duration_ms(self):
        session = _make_session()
        recorder = StepRecorder(session, "parser")
        recorder.start()
        step = recorder.finish()
        assert step.duration_ms is not None
        assert step.duration_ms >= 0

    def test_finish_derives_status_from_counts(self):
        session = _make_session()
        recorder = StepRecorder(session, "parser")
        recorder.start()
        step = recorder.finish(records_processed=10, records_failed=0)
        assert step.status == PipelineStatus.SUCCESS

    def test_finish_partial_status(self):
        session = _make_session()
        recorder = StepRecorder(session, "parser")
        recorder.start()
        step = recorder.finish(records_processed=8, records_failed=2)
        assert step.status == PipelineStatus.PARTIAL

    def test_finish_failed_status(self):
        session = _make_session()
        recorder = StepRecorder(session, "parser")
        recorder.start()
        step = recorder.finish(records_processed=0, records_failed=10)
        assert step.status == PipelineStatus.FAILED

    def test_finish_explicit_status_overrides_derived(self):
        session = _make_session()
        recorder = StepRecorder(session, "parser")
        recorder.start()
        step = recorder.finish(
            records_processed=0, records_failed=0,
            status=PipelineStatus.PARTIAL,
        )
        assert step.status == PipelineStatus.PARTIAL

    def test_step_name_stored(self):
        session = _make_session()
        recorder = StepRecorder(session, "nlp_articles", batch_limit=100)
        recorder.start()
        added = session.add.call_args[0][0]
        assert added.step_name == "nlp_articles"

    def test_metadata_stored(self):
        session = _make_session()
        recorder = StepRecorder(session, "parser", batch_limit=200, enable_llm=False)
        recorder.start()
        added = session.add.call_args[0][0]
        assert added.step_metadata == {"batch_limit": 200, "enable_llm": False}

    def test_no_metadata_stores_none(self):
        session = _make_session()
        recorder = StepRecorder(session, "analytics")
        recorder.start()
        added = session.add.call_args[0][0]
        assert added.step_metadata is None

    def test_pipeline_run_id_forwarded(self):
        import uuid
        run_id = uuid.uuid4()
        session = _make_session()
        recorder = StepRecorder(session, "parser", pipeline_run_id=run_id)
        recorder.start()
        added = session.add.call_args[0][0]
        assert added.pipeline_run_id == run_id


# ---------------------------------------------------------------------------
# record_step — context manager
# ---------------------------------------------------------------------------

class TestRecordStep:
    def test_yields_pipeline_step_run(self):
        session = _make_session()
        with record_step(session, "parser") as step:
            assert isinstance(step, PipelineStepRun)

    def test_step_name_set(self):
        session = _make_session()
        with record_step(session, "nlp_car_reviews") as step:
            assert step.step_name == "nlp_car_reviews"

    def test_auto_success_if_no_exception(self):
        session = _make_session()
        with record_step(session, "analytics") as step:
            pass
        assert step.status == PipelineStatus.SUCCESS

    def test_caller_can_override_status(self):
        session = _make_session()
        with record_step(session, "parser") as step:
            step.status = PipelineStatus.PARTIAL
        assert step.status == PipelineStatus.PARTIAL

    def test_exception_marks_failed(self):
        session = _make_session()
        with pytest.raises(ValueError):
            with record_step(session, "parser") as step:
                raise ValueError("boom")
        assert step.status == PipelineStatus.FAILED

    def test_exception_increments_error_count(self):
        session = _make_session()
        with pytest.raises(RuntimeError):
            with record_step(session, "parser") as step:
                raise RuntimeError("fail")
        assert step.error_count >= 1

    def test_finished_at_set_on_exit(self):
        session = _make_session()
        with record_step(session, "analytics") as step:
            pass
        assert step.finished_at is not None

    def test_duration_ms_computed(self):
        session = _make_session()
        with record_step(session, "analytics") as step:
            pass
        assert step.duration_ms is not None
        assert step.duration_ms >= 0

    def test_metadata_passed_as_kwargs(self):
        session = _make_session()
        with record_step(session, "parser", batch_limit=500) as step:
            pass
        assert step.step_metadata == {"batch_limit": 500}

    def test_flush_called_on_entry_and_exit(self):
        session = _make_session()
        with record_step(session, "parser") as step:
            pass
        assert session.flush.call_count >= 2  # once on entry, once on exit
