"""
analytics/aggregators.py
------------------------
High-level metric aggregation functions.

Each function receives an open SQLAlchemy session, executes aggregation
queries against the domain tables, and upserts results into the analytics
tables defined in database/models.py.

Public API:
    compute_brand_reputation(session) -> dict
        Join car_brands → car_models → car_reviews → car_review_nlp,
        group by (brand_id, calendar month), and upsert into:
          - brand_reputation_scores
          - sentiment_trends
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict

from sqlalchemy import case, cast, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Session

from database.enums import SentimentLabel
from database.models import (
    BrandReputationScore,
    CarBrand,
    CarModel,
    CarReview,
    CarReviewNlp,
    SentimentTrend,
)

logger = logging.getLogger("analytics.aggregators")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_period_date(raw) -> date:
    """Coerce a date_trunc result (datetime or date) to a ``date`` object."""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    # Fallback: parse string representation from some DB drivers
    return date.fromisoformat(str(raw)[:10])


def _upsert_reputation(
    session: Session,
    brand_id: uuid.UUID,
    period_date: date,
    avg_rating,
    avg_sentiment_score,
    review_count: int,
    now: datetime,
    data_origin: str = "all",
) -> bool:
    """Insert or update one BrandReputationScore row.  Returns True if inserted."""
    existing = (
        session.query(BrandReputationScore)
        .filter_by(brand_id=brand_id, period_date=period_date, data_origin=data_origin)
        .first()
    )
    avg_r = float(avg_rating) if avg_rating is not None else None
    avg_s = float(avg_sentiment_score) if avg_sentiment_score is not None else None

    if existing:
        existing.avg_rating = avg_r
        existing.avg_sentiment_score = avg_s
        existing.review_count = review_count
        existing.computed_at = now
        return False

    session.add(
        BrandReputationScore(
            brand_id=brand_id,
            period_date=period_date,
            avg_rating=avg_r,
            avg_sentiment_score=avg_s,
            review_count=review_count,
            data_origin=data_origin,
            computed_at=now,
        )
    )
    return True


def _upsert_sentiment_trend(
    session: Session,
    brand_id: uuid.UUID,
    period_date: date,
    positive_count: int,
    neutral_count: int,
    negative_count: int,
    avg_sentiment_score,
    now: datetime,
    data_origin: str = "all",
) -> bool:
    """Insert or update one SentimentTrend row.  Returns True if inserted."""
    existing = (
        session.query(SentimentTrend)
        .filter_by(brand_id=brand_id, period_date=period_date, data_origin=data_origin)
        .first()
    )
    avg_s = float(avg_sentiment_score) if avg_sentiment_score is not None else None

    if existing:
        existing.positive_count = positive_count
        existing.neutral_count = neutral_count
        existing.negative_count = negative_count
        existing.avg_sentiment_score = avg_s
        existing.computed_at = now
        return False

    session.add(
        SentimentTrend(
            brand_id=brand_id,
            period_date=period_date,
            positive_count=positive_count,
            neutral_count=neutral_count,
            negative_count=negative_count,
            avg_sentiment_score=avg_s,
            data_origin=data_origin,
            computed_at=now,
        )
    )
    return True


# ---------------------------------------------------------------------------
# Public aggregation functions
# ---------------------------------------------------------------------------

def _run_aggregation_query(session: Session, origin_filter: str | None = None):
    """Run the aggregation query, optionally filtered by data_origin.

    Args:
        session: Active SQLAlchemy session.
        origin_filter: If set, filter car_reviews to this data_origin value.
                       If None, include all reviews (origin='all').

    Returns:
        List of aggregated rows.
    """
    review_ts = cast(CarReview.review_date, TIMESTAMP)
    period_expr = func.date_trunc("month", review_ts)

    q = (
        session.query(
            CarBrand.id.label("brand_id"),
            CarBrand.name.label("brand_name"),
            period_expr.label("period_month"),
            func.avg(CarReview.rating).label("avg_rating"),
            func.avg(CarReviewNlp.sentiment_score).label("avg_sentiment_score"),
            func.count(CarReview.id).label("review_count"),
            func.count(
                case((CarReviewNlp.sentiment_label == SentimentLabel.POSITIVE, 1))
            ).label("positive_count"),
            func.count(
                case((CarReviewNlp.sentiment_label == SentimentLabel.NEUTRAL, 1))
            ).label("neutral_count"),
            func.count(
                case((CarReviewNlp.sentiment_label == SentimentLabel.NEGATIVE, 1))
            ).label("negative_count"),
        )
        .join(CarModel, CarBrand.id == CarModel.brand_id)
        .join(CarReview, CarModel.id == CarReview.model_id)
        .outerjoin(CarReviewNlp, CarReview.id == CarReviewNlp.review_id)
        .filter(CarReview.review_date.isnot(None))
    )

    if origin_filter is not None:
        q = q.filter(CarReview.data_origin == origin_filter)

    return (
        q.group_by(CarBrand.id, CarBrand.name, period_expr)
        .order_by(CarBrand.name, period_expr)
        .all()
    )


def compute_brand_reputation(session: Session) -> Dict[str, Any]:
    """Compute monthly brand reputation metrics, provenance-aware.

    Runs the aggregation three times:
      1. origin='all'     — all reviews combined (backward compat)
      2. origin='scraped' — real/live reviews only
      3. origin='reference'  — reference/demo data reviews only

    Each pass upserts rows with the corresponding ``data_origin`` tag
    into ``brand_reputation_scores`` and ``sentiment_trends``.

    Args:
        session: Active SQLAlchemy Session (caller owns commit/rollback).

    Returns:
        dict with summary metrics.
    """
    logger.info("Starting provenance-aware compute_brand_reputation …")
    now = datetime.now(timezone.utc)

    rep_inserted = rep_updated = trend_inserted = trend_updated = 0
    total_groups = 0

    # Compute for each provenance slice
    for origin_filter, origin_label in [
        (None, "all"),
        ("scraped", "scraped"),
        ("reference", "reference"),
    ]:
        rows = _run_aggregation_query(session, origin_filter)
        logger.info(
            "Aggregation [%s] returned %d (brand, month) group(s).",
            origin_label, len(rows),
        )
        total_groups += len(rows)

        for row in rows:
            period_date = _to_period_date(row.period_month)

            inserted = _upsert_reputation(
                session=session,
                brand_id=row.brand_id,
                period_date=period_date,
                avg_rating=row.avg_rating,
                avg_sentiment_score=row.avg_sentiment_score,
                review_count=int(row.review_count),
                now=now,
                data_origin=origin_label,
            )
            if inserted:
                rep_inserted += 1
            else:
                rep_updated += 1

            inserted = _upsert_sentiment_trend(
                session=session,
                brand_id=row.brand_id,
                period_date=period_date,
                positive_count=int(row.positive_count),
                neutral_count=int(row.neutral_count),
                negative_count=int(row.negative_count),
                avg_sentiment_score=row.avg_sentiment_score,
                now=now,
                data_origin=origin_label,
            )
            if inserted:
                trend_inserted += 1
            else:
                trend_updated += 1

            session.flush()

    metrics: Dict[str, Any] = {
        "brand_periods_found": total_groups,
        "reputation_inserted": rep_inserted,
        "reputation_updated": rep_updated,
        "trend_inserted": trend_inserted,
        "trend_updated": trend_updated,
    }
    logger.info(
        "compute_brand_reputation complete — %s",
        ", ".join(f"{k}={v}" for k, v in metrics.items()),
    )
    return metrics
