"""
tests/test_nlp_pipeline.py
---------------------------
Unit tests for nlp/nlp_pipeline.py

Uses mock SQLAlchemy sessions so no real database connection is needed.
Verifies metrics shape, skip/fail counts, and DB interaction contracts.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from nlp.nlp_pipeline import NlpPipeline
from database.enums import EntityDomain, SentimentLabel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_car_review(review_id: int, title: str = "Great car", text: str = "Excellent vehicle"):
    r = MagicMock()
    r.id = review_id
    r.review_title = title
    r.review_text = text
    return r


def _make_insurance_review(review_id: int, title: str = "Good insurer", text: str = "Fast claims"):
    r = MagicMock()
    r.id = review_id
    r.review_title = title
    r.review_text = text
    return r


def _make_article(article_id: int, title: str = "Market trends 2025", body: str = "EV adoption growing"):
    a = MagicMock()
    a.id = article_id
    a.title = title
    a.body_text = body
    return a


def _build_session(query_results=None):
    """Return a mock session where .query(...).filter(...).all() returns query_results."""
    session = MagicMock()
    query_results = query_results or []

    # Chain: .query().filter().order_by().limit().all()
    (
        session.query.return_value
        .filter.return_value
        .order_by.return_value
        .limit.return_value
        .all.return_value
    ) = query_results

    # _get_or_create_topic / _get_or_create_complaint → return None so new ones are created
    session.query.return_value.filter.return_value.first.return_value = None

    mock_topic = MagicMock()
    mock_topic.id = 1
    session.add.return_value = None
    session.flush.return_value = None
    session.commit.return_value = None
    session.rollback.return_value = None
    return session


# ---------------------------------------------------------------------------
# process_car_reviews
# ---------------------------------------------------------------------------

class TestProcessCarReviews:
    def test_returns_metrics_dict(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_car_reviews(limit=10)
        assert isinstance(metrics, dict)

    def test_metrics_keys_present(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_car_reviews(limit=10)
        assert "records_processed" in metrics
        assert "records_failed" in metrics
        assert "records_skipped" in metrics
        assert "processing_time_seconds" in metrics

    def test_empty_db_returns_zeros(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_car_reviews(limit=10)
        assert metrics["records_processed"] == 0
        assert metrics["records_failed"] == 0
        assert metrics["records_skipped"] == 0

    def test_processing_time_is_non_negative(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_car_reviews(limit=10)
        assert metrics["processing_time_seconds"] >= 0.0

    def test_empty_text_increments_skipped(self):
        review = _make_car_review(1, title="", text="")
        session = _build_session([review])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_car_reviews(limit=10)
        assert metrics["records_skipped"] == 1
        assert metrics["records_processed"] == 0

    def test_session_commit_called(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        pipeline.process_car_reviews(limit=10)
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# process_insurance_reviews
# ---------------------------------------------------------------------------

class TestProcessInsuranceReviews:
    def test_returns_metrics_dict(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_insurance_reviews(limit=10)
        assert isinstance(metrics, dict)

    def test_metrics_keys_present(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_insurance_reviews(limit=10)
        for key in ("records_processed", "records_failed", "records_skipped", "processing_time_seconds"):
            assert key in metrics

    def test_empty_text_increments_skipped(self):
        review = _make_insurance_review(1, title="", text="")
        session = _build_session([review])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_insurance_reviews(limit=10)
        assert metrics["records_skipped"] == 1

    def test_session_commit_called(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        pipeline.process_insurance_reviews(limit=10)
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# process_articles
# ---------------------------------------------------------------------------

class TestProcessArticles:
    def test_returns_metrics_dict(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_articles(limit=10)
        assert isinstance(metrics, dict)

    def test_metrics_keys_present(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_articles(limit=10)
        for key in ("records_processed", "records_failed", "records_skipped", "processing_time_seconds"):
            assert key in metrics

    def test_empty_text_increments_skipped(self):
        article = _make_article(1, title="", body="")
        session = _build_session([article])
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_articles(limit=10)
        assert metrics["records_skipped"] == 1

    def test_session_commit_called(self):
        session = _build_session([])
        pipeline = NlpPipeline(session=session)
        pipeline.process_articles(limit=10)
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# NlpPipeline constructor
# ---------------------------------------------------------------------------

class TestNlpPipelineConstructor:
    def test_default_model_version(self):
        session = MagicMock()
        pipeline = NlpPipeline(session=session)
        assert pipeline.model_version == "distilbert-sst2-v1"

    def test_custom_model_version(self):
        session = MagicMock()
        pipeline = NlpPipeline(session=session, model_version="distilbert-v2")
        assert pipeline.model_version == "distilbert-v2"

    def test_session_stored(self):
        session = MagicMock()
        pipeline = NlpPipeline(session=session)
        assert pipeline.session is session
