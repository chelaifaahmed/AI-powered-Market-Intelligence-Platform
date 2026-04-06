"""
tests/test_api_operational.py
------------------------------
Tests for Phase 10 operational FastAPI endpoints.

Uses TestClient with monkeypatched DB sessions — no real DB required.
Covers response shapes, pagination, status codes, and edge cases.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from database.enums import PipelineStatus, RunStatus, TaskStatus

client = TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow():
    return datetime.now(timezone.utc)


def _mock_pipeline_run(run_id=None, task_name="parser_pipeline_batch", status=PipelineStatus.SUCCESS):
    r = MagicMock()
    r.id = run_id or uuid.uuid4()
    r.task_name = task_name
    r.started_at = _utcnow()
    r.finished_at = _utcnow()
    r.status = status
    r.records_scraped = 10
    r.records_stored = 8
    r.error_message = None
    r.created_at = _utcnow()
    r.steps = []
    return r


def _mock_step_run(step_name="parser", status=PipelineStatus.SUCCESS):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.pipeline_run_id = None
    s.step_name = step_name
    s.status = status
    s.started_at = _utcnow()
    s.finished_at = _utcnow()
    s.duration_ms = 1234
    s.records_seen = 10
    s.records_processed = 8
    s.records_skipped = 1
    s.records_failed = 1
    s.records_inserted = 8
    s.error_count = 1
    s.step_metadata = {"batch_limit": 500}
    s.created_at = _utcnow()
    return s


def _mock_session_ctx(session):
    """Return a context manager that yields the given mock session."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=session)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# GET /api/pipeline/runs (existing — still works)
# ---------------------------------------------------------------------------

class TestListPipelineRuns:
    def test_returns_list(self):
        session = MagicMock()
        run = _mock_pipeline_run()
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = [run]

        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/runs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_empty_db_returns_empty_list(self):
        session = MagicMock()
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/runs")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/pipeline/runs/{id}
# ---------------------------------------------------------------------------

class TestGetPipelineRunDetail:
    def test_returns_run_with_steps(self):
        run_id = uuid.uuid4()
        session = MagicMock()
        run = _mock_pipeline_run(run_id=run_id)
        step = _mock_step_run()
        session.get.return_value = run
        session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [step]

        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get(f"/api/pipeline/runs/{run_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(run_id)
        assert "steps" in body
        assert isinstance(body["steps"], list)

    def test_404_for_missing_run(self):
        session = MagicMock()
        session.get.return_value = None

        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get(f"/api/pipeline/runs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_steps_contain_expected_fields(self):
        run_id = uuid.uuid4()
        session = MagicMock()
        run = _mock_pipeline_run(run_id=run_id)
        step = _mock_step_run()
        session.get.return_value = run
        session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [step]

        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get(f"/api/pipeline/runs/{run_id}")

        body = resp.json()
        if body["steps"]:
            s = body["steps"][0]
            for field in ("step_name", "status", "records_processed", "records_failed", "duration_ms"):
                assert field in s, f"Missing field '{field}' in step"

    def test_run_with_no_steps_returns_empty_steps_list(self):
        run_id = uuid.uuid4()
        session = MagicMock()
        run = _mock_pipeline_run(run_id=run_id)
        session.get.return_value = run
        session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get(f"/api/pipeline/runs/{run_id}")

        assert resp.status_code == 200
        assert resp.json()["steps"] == []


# ---------------------------------------------------------------------------
# GET /api/pipeline/status
# ---------------------------------------------------------------------------

class TestPipelineStatus:
    def _build_session(self, counts=None):
        """Build a mock session for the pipeline_status endpoint."""
        c = counts or {}
        session = MagicMock()
        # Each .count() call returns a different value based on the model queried
        session.query.return_value.count.return_value = c.get("default", 0)
        session.query.return_value.filter.return_value.count.return_value = 0
        session.query.return_value.filter.return_value.filter.return_value.count.return_value = 0
        session.query.return_value.group_by.return_value.all.return_value = []
        return session

    def test_returns_200(self):
        session = self._build_session()
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/status")
        assert resp.status_code == 200

    def test_response_has_expected_keys(self):
        session = self._build_session()
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/status")
        body = resp.json()
        assert "raw_pages" in body
        assert "nlp_coverage" in body
        assert "data_quality" in body
        assert "pipeline_steps" in body

    def test_nlp_coverage_keys_present(self):
        session = self._build_session()
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/status")
        cov = resp.json()["nlp_coverage"]
        assert "car_reviews" in cov
        assert "insurance_reviews" in cov

    def test_zero_reviews_gives_zero_coverage_pct(self):
        session = self._build_session({"default": 0})
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/status")
        cov = resp.json()["nlp_coverage"]
        assert cov["car_reviews"]["coverage_pct"] == 0.0


# ---------------------------------------------------------------------------
# GET /api/pipeline/quality
# ---------------------------------------------------------------------------

class TestPipelineQuality:
    def _build_session(self):
        session = MagicMock()
        session.query.return_value.count.return_value = 0
        session.query.return_value.filter.return_value.count.return_value = 0
        session.query.return_value.filter.return_value.filter.return_value.count.return_value = 0
        session.query.return_value.group_by.return_value.order_by.return_value.all.return_value = []
        return session

    def test_returns_200(self):
        session = self._build_session()
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/quality")
        assert resp.status_code == 200

    def test_response_schema(self):
        session = self._build_session()
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/quality")
        body = resp.json()
        for field in (
            "total_rejections", "raw_pages_unparsed", "raw_pages_parse_errors",
            "car_review_nlp_coverage_pct", "insurance_review_nlp_coverage_pct",
            "by_entity_type",
        ):
            assert field in body, f"Missing field: {field}"

    def test_empty_db_zeros(self):
        session = self._build_session()
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/quality")
        body = resp.json()
        assert body["total_rejections"] == 0
        assert body["by_entity_type"] == []


# ---------------------------------------------------------------------------
# GET /api/pipeline/failures
# ---------------------------------------------------------------------------

class TestPipelineFailures:
    def _build_session(self, dql_rows=None, err_rows=None):
        session = MagicMock()
        # data_quality_log query chain
        (session.query.return_value
         .order_by.return_value.all.return_value) = dql_rows or []
        return session

    def test_returns_200(self):
        session = MagicMock()
        session.query.return_value.order_by.return_value.all.return_value = []
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/failures")
        assert resp.status_code == 200

    def test_response_is_paged(self):
        session = MagicMock()
        session.query.return_value.order_by.return_value.all.return_value = []
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/failures")
        body = resp.json()
        assert "total" in body
        assert "items" in body
        assert "limit" in body
        assert "offset" in body

    def test_empty_returns_zero_total(self):
        session = MagicMock()
        session.query.return_value.order_by.return_value.all.return_value = []
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/failures")
        assert resp.json()["total"] == 0

    def test_limit_param_respected(self):
        session = MagicMock()
        session.query.return_value.order_by.return_value.all.return_value = []
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/pipeline/failures?limit=10")
        assert resp.json()["limit"] == 10


# ---------------------------------------------------------------------------
# GET /api/sources/health
# ---------------------------------------------------------------------------

class TestSourcesHealth:
    def _mock_task(self, name="caranddriver_scraper"):
        t = MagicMock()
        t.id = uuid.uuid4()
        t.task_name = name
        t.status = TaskStatus.COMPLETED
        return t

    def test_returns_200(self):
        session = MagicMock()
        task = self._mock_task()
        session.query.return_value.order_by.return_value.all.return_value = [task]
        # scraping_runs query
        session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        # ScraperHealthMetric query
        session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/sources/health")
        assert resp.status_code == 200

    def test_returns_list(self):
        session = MagicMock()
        session.query.return_value.order_by.return_value.all.return_value = []
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/sources/health")
        assert isinstance(resp.json(), list)

    def test_empty_tasks_returns_empty_list(self):
        session = MagicMock()
        session.query.return_value.order_by.return_value.all.return_value = []
        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/sources/health")
        assert resp.json() == []

    def test_source_entry_has_expected_fields(self):
        session = MagicMock()
        task = self._mock_task("trustpilot_scraper")
        session.query.return_value.order_by.return_value.all.return_value = [task]
        session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/sources/health")

        body = resp.json()
        assert len(body) == 1
        entry = body[0]
        for field in (
            "scraper_name", "total_runs", "successful_runs", "failed_runs",
            "last_run_status", "consecutive_failures",
        ):
            assert field in entry, f"Missing field: {field}"

    def test_no_runs_gives_zero_counts(self):
        session = MagicMock()
        task = self._mock_task("test_scraper")
        session.query.return_value.order_by.return_value.all.return_value = [task]
        session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        with patch("api.main.get_db_session", return_value=_mock_session_ctx(session)):
            resp = client.get("/api/sources/health")

        entry = resp.json()[0]
        assert entry["total_runs"] == 0
        assert entry["successful_runs"] == 0
        assert entry["consecutive_failures"] == 0
