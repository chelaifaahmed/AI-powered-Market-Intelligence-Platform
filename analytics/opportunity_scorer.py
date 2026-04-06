"""
analytics/opportunity_scorer.py
-------------------------------
Rule-based opportunity scoring for TEAMWILL sales targeting.

Scores each InsuranceCompany and CarBrand on 4 dimensions (total 100 points):
  1. TEAMWILL Fit (0-40)  — do their complaints match what TEAMWILL's ERP solves?
  2. Sentiment Trend (0-25) — is the company getting worse over time?
  3. Market Presence (0-20) — is the company big enough to be a real target?
  4. Complaint Intensity (0-15) — raw negative review rate (sector-adjusted)

Signal strength thresholds: >= 70 strong, >= 45 moderate, < 45 weak.

Public API:
    compute_opportunity_signals(session) -> list[dict]
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from database.models import (
    CarBrand,
    CarModel,
    CarReview,
    CarReviewNlp,
    ComplaintType,
    InsuranceCompany,
    InsuranceReview,
    InsuranceReviewNlp,
    OpportunitySignal,
    SentimentTrend,
)

logger = logging.getLogger("analytics.opportunity_scorer")


# ---------------------------------------------------------------------------
# TEAMWILL fit mapping — complaint labels → relevance score
# ---------------------------------------------------------------------------

_HIGH_FIT_KEYWORDS = [
    "claims processing", "claims delay", "claim denied",
    "service tracking", "after sales service",
    "policy management", "policy billing", "policy pricing",
    "customer service", "response time",
]

_MEDIUM_FIT_KEYWORDS = [
    "engine issues", "battery issues", "technical issues",
    "repair quality", "maintenance",
]

_LOW_FIT_KEYWORDS = [
    "pricing", "price increase", "value for money",
    "delivery", "shipping",
]


def _match_fit(label: str) -> Tuple[int, str]:
    """Match a complaint label to a TEAMWILL fit tier. Returns (score, tier)."""
    low = label.lower().strip()
    for kw in _HIGH_FIT_KEYWORDS:
        if kw in low:
            return 40, "high"
    for kw in _MEDIUM_FIT_KEYWORDS:
        if kw in low:
            return 25, "medium"
    for kw in _LOW_FIT_KEYWORDS:
        if kw in low:
            return 10, "low"
    return 10, "low"  # unknown complaint type → low default


# ---------------------------------------------------------------------------
# Dimension 1: TEAMWILL Fit Score (0-40)
# ---------------------------------------------------------------------------

def score_teamwill_fit(complaint_labels: List[str]) -> Tuple[int, dict]:
    """Score how well the entity's complaints match TEAMWILL's ERP capabilities."""
    if not complaint_labels:
        return 5, {
            "score": 5,
            "matched_category": None,
            "reason": "No complaint data detected — minimal fit signal",
        }

    best_score = 0
    best_label = ""
    best_tier = "none"
    for label in complaint_labels:
        s, tier = _match_fit(label)
        if s > best_score:
            best_score = s
            best_label = label
            best_tier = tier

    reasons = {
        "high": f"Customer complaints focus on {best_label} — direct ERP fit",
        "medium": f"Complaints about {best_label} — moderate ERP relevance",
        "low": f"Complaints about {best_label} — low direct ERP relevance",
    }

    return best_score, {
        "score": best_score,
        "matched_category": best_label,
        "reason": reasons.get(best_tier, f"Complaint: {best_label}"),
    }


# ---------------------------------------------------------------------------
# Dimension 2: Sentiment Trend Direction (0-25)
# ---------------------------------------------------------------------------

def score_trend_brand(session: Session, brand_id: uuid.UUID) -> Tuple[int, dict]:
    """Compare avg sentiment last 3 months vs prior 3 months for a brand."""
    trends = (
        session.query(SentimentTrend)
        .filter(SentimentTrend.brand_id == brand_id, SentimentTrend.data_origin == "all")
        .order_by(SentimentTrend.period_date.desc())
        .limit(6)
        .all()
    )
    return _compute_trend_score(trends)


def score_trend_insurance(session: Session, company_id: uuid.UUID) -> Tuple[int, dict]:
    """Compute trend from insurance review sentiment scores over time."""
    nlp_rows = (
        session.query(InsuranceReviewNlp.sentiment_score, InsuranceReview.review_date)
        .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
        .filter(InsuranceReview.company_id == company_id)
        .filter(InsuranceReview.review_date.isnot(None))
        .order_by(InsuranceReview.review_date.desc())
        .all()
    )
    if len(nlp_rows) < 4:
        return 12, {
            "score": 12,
            "direction": "unknown",
            "change_pct": 0,
            "reason": "Insufficient trend data — moderate default",
        }

    mid = len(nlp_rows) // 2
    recent_scores = [float(r[0]) for r in nlp_rows[:mid] if r[0] is not None]
    older_scores = [float(r[0]) for r in nlp_rows[mid:] if r[0] is not None]

    if not recent_scores or not older_scores:
        return 12, {
            "score": 12,
            "direction": "unknown",
            "change_pct": 0,
            "reason": "Insufficient sentiment data — moderate default",
        }

    return _evaluate_trend(recent_scores, older_scores)


def _compute_trend_score(trends) -> Tuple[int, dict]:
    """Shared logic for SentimentTrend-based trend scoring."""
    if len(trends) < 2:
        return 12, {
            "score": 12,
            "direction": "unknown",
            "change_pct": 0,
            "reason": "No trend data available — moderate default",
        }

    recent = trends[:3]
    older = trends[3:6]

    recent_scores = [float(t.avg_sentiment_score) for t in recent if t.avg_sentiment_score is not None]
    older_scores = [float(t.avg_sentiment_score) for t in older if t.avg_sentiment_score is not None]

    if not recent_scores or not older_scores:
        return 12, {
            "score": 12,
            "direction": "unknown",
            "change_pct": 0,
            "reason": "Insufficient sentiment data — moderate default",
        }

    return _evaluate_trend(recent_scores, older_scores)


def _evaluate_trend(recent_scores: list, older_scores: list) -> Tuple[int, dict]:
    """Core trend evaluation: recent vs older average sentiment."""
    recent_avg = sum(recent_scores) / len(recent_scores)
    older_avg = sum(older_scores) / len(older_scores)

    if older_avg == 0:
        return 12, {
            "score": 12,
            "direction": "unknown",
            "change_pct": 0,
            "reason": "Baseline sentiment is zero — cannot compute trend",
        }

    pct_change = ((recent_avg - older_avg) / abs(older_avg)) * 100

    if pct_change < -15:
        score, direction = 25, "declining_fast"
        reason = f"Sentiment dropped {abs(pct_change):.1f}% in last 3 months — urgent"
    elif pct_change < -5:
        score, direction = 18, "declining"
        reason = f"Sentiment dipped {abs(pct_change):.1f}% — watch closely"
    elif pct_change <= 5:
        score, direction = 10, "stable"
        reason = f"Sentiment stable ({pct_change:+.1f}%) — neutral signal"
    else:
        score, direction = 3, "improving"
        reason = f"Sentiment improving ({pct_change:+.1f}%) — deprioritize"

    return score, {
        "score": score,
        "direction": direction,
        "change_pct": round(pct_change, 1),
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Dimension 3: Market Presence (0-20)
# ---------------------------------------------------------------------------

def score_market_presence(review_count: int) -> Tuple[int, dict]:
    """Score based on review volume as proxy for company size."""
    if review_count > 150:
        score = 20
        reason = f"Major player with {review_count} reviews"
    elif review_count > 50:
        score = 16
        reason = f"Significant presence with {review_count} reviews"
    elif review_count > 20:
        score = 10
        reason = f"Mid-size presence with {review_count} reviews"
    elif review_count > 5:
        score = 5
        reason = f"Small presence with {review_count} reviews"
    elif review_count > 0:
        score = 2
        reason = f"Very small presence — only {review_count} reviews"
    else:
        score = 0
        reason = "No reviews found — unknown market presence"

    return score, {
        "score": score,
        "review_count": review_count,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Dimension 4: Complaint Intensity (0-15), sector-adjusted
# ---------------------------------------------------------------------------

def score_complaint_intensity(
    negative_pct: float, entity_type: str, review_count: int
) -> Tuple[int, dict]:
    """Score raw negative sentiment rate with sector-specific thresholds."""
    if review_count == 0:
        return 0, {
            "score": 0,
            "negative_pct": 0,
            "sector": entity_type,
            "reason": "No reviews — cannot assess complaint intensity",
        }

    if entity_type == "insurance":
        # Insurance: lower thresholds (more complaint-prone industry)
        if negative_pct > 60:
            score = 15
            level = "crisis"
        elif negative_pct > 40:
            score = 10
            level = "serious"
        elif negative_pct > 20:
            score = 5
            level = "moderate"
        else:
            score = 2
            level = "low"
    else:
        # Car brands: higher thresholds
        if negative_pct > 70:
            score = 15
            level = "crisis"
        elif negative_pct > 50:
            score = 10
            level = "serious"
        elif negative_pct > 30:
            score = 5
            level = "moderate"
        else:
            score = 2
            level = "low"

    return score, {
        "score": score,
        "negative_pct": round(negative_pct, 1),
        "sector": entity_type,
        "reason": f"{negative_pct:.1f}% negative — {level} level for {entity_type}",
    }


# ---------------------------------------------------------------------------
# NLP data gathering helpers
# ---------------------------------------------------------------------------

def _get_complaint_labels(session: Session, nlp_rows) -> List[str]:
    """Extract top complaint type labels from NLP result rows."""
    type_ids = [r.complaint_type_id for r in nlp_rows if r.complaint_type_id is not None]
    if not type_ids:
        return []
    top_ids = [tid for tid, _ in Counter(type_ids).most_common(3)]
    labels = []
    for tid in top_ids:
        ct = session.get(ComplaintType, tid)
        if ct:
            labels.append(ct.label)
    return labels


def _negative_pct(nlp_rows) -> float:
    """Compute percentage of negative sentiment in NLP results."""
    from database.enums import SentimentLabel
    total = len(nlp_rows)
    if total == 0:
        return 0.0
    negative = sum(1 for r in nlp_rows if r.sentiment_label == SentimentLabel.NEGATIVE)
    return (negative / total) * 100


# ---------------------------------------------------------------------------
# Signal strength
# ---------------------------------------------------------------------------

def _signal_strength(overall: float) -> str:
    if overall >= 70:
        return "strong"
    elif overall >= 45:
        return "moderate"
    return "weak"


# ---------------------------------------------------------------------------
# Upsert helper (matches aggregators.py pattern)
# ---------------------------------------------------------------------------

def _upsert_signal(session: Session, data: dict) -> bool:
    """Insert or update an OpportunitySignal row. Returns True if inserted.

    Analyst-sourced signals (data_origin='analyst' in score_reasoning) are
    preserved when the review-based computed score is lower — the analyst
    assessment is considered more informed for companies with no reviews.
    If the company gains real review data that produces a higher score,
    the computed score takes precedence.
    """
    existing = (
        session.query(OpportunitySignal)
        .filter_by(entity_type=data["entity_type"], entity_id=data["entity_id"])
        .first()
    )
    if existing:
        existing_origin = (existing.score_reasoning or {}).get("data_origin")
        new_score = data.get("overall_score", 0)

        # Preserve analyst signals when computed score is lower
        if existing_origin == "analyst" and new_score < float(existing.overall_score):
            logger.info(
                "Preserving analyst signal for %s (analyst=%s > computed=%s)",
                data.get("entity_name"), existing.overall_score, new_score,
            )
            # Update data dict in-place so callers see the preserved values
            data["overall_score"] = float(existing.overall_score)
            data["complaint_score"] = float(existing.complaint_score)
            data["sentiment_drop_score"] = float(existing.sentiment_drop_score)
            data["review_volume_score"] = float(existing.review_volume_score)
            data["signal_strength"] = existing.signal_strength
            data["score_reasoning"] = existing.score_reasoning
            return False

        # If overwriting an analyst signal, carry forward the analyst metadata
        if existing_origin == "analyst":
            old_reasoning = existing.score_reasoning or {}
            new_reasoning = data.get("score_reasoning", {})
            for key in ("briefing_text", "why_text", "erp_module_recommendation"):
                if key in old_reasoning and key not in new_reasoning:
                    new_reasoning[key] = old_reasoning[key]
            new_reasoning["data_origin"] = "computed"
            data["score_reasoning"] = new_reasoning

        for key, val in data.items():
            if key != "id":
                setattr(existing, key, val)
        return False

    session.add(OpportunitySignal(**data))
    return True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_opportunity_signals(session: Session) -> List[Dict[str, Any]]:
    """
    Compute opportunity scores for all InsuranceCompanies and CarBrands.
    4-dimension rule-based model tuned for TEAMWILL's ERP/leasing business.
    Upserts into opportunity_signals table.

    Returns list of signal dicts for summary reporting.
    """
    logger.info("Starting opportunity signal computation (4-dimension model) ...")
    now = datetime.now(timezone.utc)
    signals: List[Dict[str, Any]] = []
    inserted = updated = 0

    # ----- Insurance Companies -----
    companies = session.query(InsuranceCompany).filter(InsuranceCompany.is_active.is_(True)).all()
    for company in companies:
        total_reviews = (
            session.query(InsuranceReview)
            .filter(InsuranceReview.company_id == company.id)
            .count()
        )

        # Get NLP data
        nlp_rows = (
            session.query(InsuranceReviewNlp)
            .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
            .filter(InsuranceReview.company_id == company.id)
            .all()
        )
        complaint_labels = _get_complaint_labels(session, nlp_rows)
        neg_pct = _negative_pct(nlp_rows)

        # 4 dimensions
        d1_score, d1_detail = score_teamwill_fit(complaint_labels)
        d2_score, d2_detail = score_trend_insurance(session, company.id)
        d3_score, d3_detail = score_market_presence(total_reviews)
        d4_score, d4_detail = score_complaint_intensity(neg_pct, "insurance", total_reviews)

        overall = d1_score + d2_score + d3_score + d4_score
        strength = _signal_strength(overall)

        reasoning = {
            "teamwill_fit": d1_detail,
            "trend": d2_detail,
            "market_presence": d3_detail,
            "complaint_intensity": d4_detail,
            "total": overall,
            "signal_strength": strength,
        }

        data = {
            "entity_type": "insurance",
            "entity_id": company.id,
            "entity_name": company.name,
            "region": company.region,
            "overall_score": overall,
            "complaint_score": d1_score,          # TEAMWILL fit
            "sentiment_drop_score": d2_score,     # trend direction
            "review_volume_score": d3_score,      # market presence
            "top_complaint_types": complaint_labels[:3] if complaint_labels else None,
            "score_reasoning": reasoning,
            "signal_strength": strength,
            "sector_percentile": None,  # filled by _apply_sector_benchmarks
            "computed_at": now,
        }

        if _upsert_signal(session, data):
            inserted += 1
        else:
            updated += 1
        signals.append(data)
        session.flush()

    # ----- Car Brands -----
    brands = session.query(CarBrand).filter(CarBrand.is_active.is_(True)).all()
    for brand in brands:
        total_reviews = (
            session.query(CarReview)
            .join(CarModel, CarReview.model_id == CarModel.id)
            .filter(CarModel.brand_id == brand.id)
            .count()
        )

        # Get NLP data
        nlp_rows = (
            session.query(CarReviewNlp)
            .join(CarReview, CarReviewNlp.review_id == CarReview.id)
            .join(CarModel, CarReview.model_id == CarModel.id)
            .filter(CarModel.brand_id == brand.id)
            .all()
        )
        complaint_labels = _get_complaint_labels(session, nlp_rows)
        neg_pct = _negative_pct(nlp_rows)

        # 4 dimensions
        d1_score, d1_detail = score_teamwill_fit(complaint_labels)
        d2_score, d2_detail = score_trend_brand(session, brand.id)
        d3_score, d3_detail = score_market_presence(total_reviews)
        d4_score, d4_detail = score_complaint_intensity(neg_pct, "brand", total_reviews)

        overall = d1_score + d2_score + d3_score + d4_score
        strength = _signal_strength(overall)

        reasoning = {
            "teamwill_fit": d1_detail,
            "trend": d2_detail,
            "market_presence": d3_detail,
            "complaint_intensity": d4_detail,
            "total": overall,
            "signal_strength": strength,
        }

        data = {
            "entity_type": "brand",
            "entity_id": brand.id,
            "entity_name": brand.name,
            "region": brand.region,
            "overall_score": overall,
            "complaint_score": d1_score,
            "sentiment_drop_score": d2_score,
            "review_volume_score": d3_score,
            "top_complaint_types": complaint_labels[:3] if complaint_labels else None,
            "score_reasoning": reasoning,
            "signal_strength": strength,
            "sector_percentile": None,  # filled by _apply_sector_benchmarks
            "computed_at": now,
        }

        if _upsert_signal(session, data):
            inserted += 1
        else:
            updated += 1
        signals.append(data)
        session.flush()

    # ----- Sector benchmarking pass -----
    _apply_sector_benchmarks(session, signals)

    # Summary
    strong = sum(1 for s in signals if s["signal_strength"] == "strong")
    moderate = sum(1 for s in signals if s["signal_strength"] == "moderate")
    weak = sum(1 for s in signals if s["signal_strength"] == "weak")

    logger.info(
        "Computed %d signals: %d strong, %d moderate, %d weak (inserted=%d, updated=%d)",
        len(signals), strong, moderate, weak, inserted, updated,
    )

    return signals


# ---------------------------------------------------------------------------
# Sector benchmarking — compute percentiles and sector context
# ---------------------------------------------------------------------------

def _apply_sector_benchmarks(session: Session, signals: List[Dict[str, Any]]) -> None:
    """
    For each sector (insurance / brand), compute averages and percentiles,
    then update score_reasoning with sector_context and persist sector_percentile.
    """
    for sector in ("insurance", "brand"):
        sector_signals = [s for s in signals if s["entity_type"] == sector]
        if not sector_signals:
            continue

        scores = [s["overall_score"] for s in sector_signals]
        avg_score = round(sum(scores) / len(scores), 1)

        # Avg negative_pct across sector
        neg_pcts = [
            s["score_reasoning"].get("complaint_intensity", {}).get("negative_pct", 0)
            for s in sector_signals
        ]
        avg_neg_pct = round(sum(neg_pcts) / len(neg_pcts), 1) if neg_pcts else 0.0

        # Sort ascending for percentile computation (higher score = more distressed)
        sorted_scores = sorted(scores)
        n = len(sorted_scores)

        for sig in sector_signals:
            score = sig["overall_score"]
            # Percentile: % of entities this entity scores higher than (more distressed)
            rank = sum(1 for x in sorted_scores if x < score)
            percentile = round((rank / n) * 100) if n > 1 else 50

            if percentile >= 75:
                perf = "below"  # below average = more distressed than peers
            elif percentile <= 25:
                perf = "above"  # above average = less distressed than peers
            else:
                perf = "average"

            sector_label = "insurance" if sector == "insurance" else "automotive"
            sector_context = {
                "sector": sector_label,
                "sector_avg_score": avg_score,
                "sector_avg_negative_pct": avg_neg_pct,
                "performance_vs_sector": perf,
                "percentile": percentile,
            }

            sig["score_reasoning"]["sector_context"] = sector_context
            sig["sector_percentile"] = percentile

            # Persist to DB
            existing = (
                session.query(OpportunitySignal)
                .filter_by(entity_type=sig["entity_type"], entity_id=sig["entity_id"])
                .first()
            )
            if existing:
                existing.sector_percentile = percentile
                existing.score_reasoning = sig["score_reasoning"]
                session.flush()
