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
) -> bool:
    """Insert or update one BrandReputationScore row.  Returns True if inserted."""
    existing = (
        session.query(BrandReputationScore)
        .filter_by(brand_id=brand_id, period_date=period_date)
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
) -> bool:
    """Insert or update one SentimentTrend row.  Returns True if inserted."""
    existing = (
        session.query(SentimentTrend)
        .filter_by(brand_id=brand_id, period_date=period_date)
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
            computed_at=now,
        )
    )
    return True


# ---------------------------------------------------------------------------
# Public aggregation functions
# ---------------------------------------------------------------------------

def compute_brand_reputation(session: Session) -> Dict[str, Any]:
    """Compute monthly brand reputation metrics and upsert into analytics tables.

    Joins:
        car_brands → car_models → car_reviews LEFT OUTER JOIN car_review_nlp

    Groups by:
        (brand_id, date_trunc('month', review_date))

    Computes per group:
        - avg_rating              — mean star rating (CarReview.rating)
        - avg_sentiment_score     — mean NLP sentiment score (CarReviewNlp.sentiment_score)
        - review_count            — total review rows
        - positive/neutral/negative_count — NLP label breakdown

    Upserts into:
        - brand_reputation_scores  (unique per brand + month)
        - sentiment_trends         (unique per brand + month)

    Args:
        session: Active SQLAlchemy Session (caller owns commit/rollback).

    Returns:
        dict with keys:
            brand_periods_found       — distinct (brand, month) groups found
            reputation_inserted       — new BrandReputationScore rows created
            reputation_updated        — existing BrandReputationScore rows updated
            trend_inserted            — new SentimentTrend rows created
            trend_updated             — existing SentimentTrend rows updated
    """
    logger.info("Starting compute_brand_reputation aggregation …")
    now = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Aggregate query: one row per (brand_id, calendar-month)
    # date_trunc requires a timestamp; CarReview.review_date is DATE so
    # we cast explicitly to avoid implicit-cast warnings on strict configs.
    # ------------------------------------------------------------------
    review_ts = cast(CarReview.review_date, TIMESTAMP)
    period_expr = func.date_trunc("month", review_ts)

    rows = (
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
        .group_by(CarBrand.id, CarBrand.name, period_expr)
        .order_by(CarBrand.name, period_expr)
        .all()
    )

    logger.info("Aggregation query returned %d (brand, month) group(s).", len(rows))

    rep_inserted = rep_updated = trend_inserted = trend_updated = 0

    for row in rows:
        period_date = _to_period_date(row.period_month)

        logger.debug(
            "Processing brand='%s' period=%s reviews=%d",
            row.brand_name, period_date, row.review_count,
        )

        inserted = _upsert_reputation(
            session=session,
            brand_id=row.brand_id,
            period_date=period_date,
            avg_rating=row.avg_rating,
            avg_sentiment_score=row.avg_sentiment_score,
            review_count=int(row.review_count),
            now=now,
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
        )
        if inserted:
            trend_inserted += 1
        else:
            trend_updated += 1

        # Flush periodically to free memory on large datasets
        session.flush()

    metrics: Dict[str, Any] = {
        "brand_periods_found": len(rows),
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
