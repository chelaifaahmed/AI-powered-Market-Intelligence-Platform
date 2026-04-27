"""
analytics/opportunity_scorer.py
--------------------------------
ML-based opportunity scoring for TEAMWILL sales targeting.

4 ML-driven dimensions (total 100 points):
  1. Article Signal     (0–35)  RAG cosine similarity × recency decay,
                                 sector-relative percentile rank
  2. Sentiment Trend    (0–25)  linear regression slope (scipy.stats.linregress),
                                 inverted sector-relative percentile
  3. Market Presence    (0–20)  log-review-count sector-relative percentile
  4. Complaint Intensity(0–20)  negative-review-pct sector-relative percentile

All normalisation is data-driven — thresholds emerge from peer distributions,
not hardcoded values.

Public API:
    compute_opportunity_signals(session) -> list[dict]
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import func, text as _t
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
)

logger = logging.getLogger("analytics.opportunity_scorer")

# ---------------------------------------------------------------------------
# Embedder — lazy, reuses main.py model if running inside the API process
# ---------------------------------------------------------------------------

_SCORER_EMBEDDER = None
_BGE_PREFIX = "Represent this sentence for searching relevant passages: "


def _get_scorer_embedder():
    global _SCORER_EMBEDDER
    if _SCORER_EMBEDDER is None:
        try:
            import api.main as _main
            if getattr(_main, "_RAG_EMBEDDER", None) is not None:
                _SCORER_EMBEDDER = _main._RAG_EMBEDDER
                return _SCORER_EMBEDDER
        except Exception:
            pass
        from sentence_transformers import SentenceTransformer
        _SCORER_EMBEDDER = SentenceTransformer("BAAI/bge-base-en-v1.5")
    return _SCORER_EMBEDDER


def _embed_for_scorer(text: str) -> np.ndarray:
    model = _get_scorer_embedder()
    emb = model.encode([_BGE_PREFIX + text], normalize_embeddings=True)
    return emb[0].astype(np.float32)


# ---------------------------------------------------------------------------
# Article data — loaded once per scoring run
# ---------------------------------------------------------------------------

_CAR_SECTOR_CATS = {
    "automotive", "EV", "ERP", "InsurTech", "Technology",
    "Regulation", "Market", "Keyword Search",
}
_INS_SECTOR_CATS = {
    "insurance", "Insurance", "ERP", "InsurTech", "business", "Technology", "Market",
}


def _load_article_data(session: Session) -> List[dict]:
    from datetime import date as date_cls
    today = datetime.now(timezone.utc).date()
    rows = session.execute(_t("""
        SELECT id::text AS id,
               embedding,
               lower(coalesce(title, '')) AS title_lc,
               category,
               coalesce(publication_date, scraped_at::date)::text AS pub_date
        FROM market_trend_articles
        WHERE embedding IS NOT NULL AND data_origin = 'scraped'
    """)).fetchall()
    result = []
    for r in rows:
        try:
            pub = date_cls.fromisoformat(r.pub_date) if r.pub_date else None
            days_old = max(0, (today - pub).days) if pub else 365
        except Exception:
            days_old = 365
        result.append({
            "id": r.id,
            "embedding": np.array(r.embedding, dtype=np.float32),
            "title": r.title_lc,
            "category": r.category or "",
            "pub_date": r.pub_date,
            "days_old": days_old,
            "recency_weight": float(np.exp(-days_old / 180.0)),
        })
    return result


# ---------------------------------------------------------------------------
# Dimension 1 — Article Signal (raw)
# ---------------------------------------------------------------------------

def _compute_article_signal_raw(
    entity_name: str,
    entity_type: str,
    article_data: List[dict],
) -> Tuple[float, List[dict]]:
    """Return (raw_signal_score, top5_articles_for_viz)."""
    if not article_data:
        return 0.0, []

    sector_cats = _CAR_SECTOR_CATS if entity_type in ("car", "brand") else _INS_SECTOR_CATS
    brand_lower = entity_name.lower()

    if entity_type in ("car", "brand"):
        query_text = (
            f"{entity_name} automotive fleet management ERP "
            f"operational failures recall defect breakdown"
        )
    else:
        query_text = (
            f"{entity_name} insurance claims management ERP "
            f"operational failures system breakdown"
        )

    try:
        q_vec = _embed_for_scorer(query_text)
    except Exception as exc:
        logger.warning("Embedding failed for %s: %s", entity_name, exc)
        return 0.0, []

    # Restrict to sector-relevant articles
    filtered = [
        a for a in article_data
        if a["category"] in sector_cats or brand_lower in a["title"]
    ]
    if not filtered:
        filtered = article_data

    matrix = np.stack([a["embedding"] for a in filtered])
    sims = matrix @ q_vec
    weights = np.array([a["recency_weight"] for a in filtered], dtype=np.float32)
    weighted = sims * weights

    # Sum of top-10 weighted sims = raw signal (unbounded positive)
    top10_idx = np.argsort(weighted)[::-1][:10]
    raw_signal = float(weighted[top10_idx].sum())

    # Top-5 by pure similarity for visualization
    top5_idx = np.argsort(sims)[::-1][:5]
    top_articles = [
        {
            "title": filtered[i]["title"],
            "similarity": round(float(sims[i]), 4),
            "pub_date": filtered[i]["pub_date"],
            "category": filtered[i]["category"],
            "days_old": filtered[i]["days_old"],
            "recency_weight": round(filtered[i]["recency_weight"], 4),
        }
        for i in top5_idx
    ]
    return raw_signal, top_articles


# ---------------------------------------------------------------------------
# Dimension 2 — Sentiment Trend (neg_pct metric + MK + polynomial)
# ---------------------------------------------------------------------------

_MIN_REVIEWS_THRESHOLD = 3  # months with fewer reviews are noise — excluded from fitting


def _compute_trend_ml(
    session: Session,
    entity_id: uuid.UUID,
    entity_type: str,
) -> Tuple[float, dict]:
    """
    Hybrid trend analysis on % negative reviews per month (robust metric):

      Raw metric  : avg_sentiment — kept for reference chart only (binary ±1, noisy)
      Clean metric: neg_pct       — fraction of reviews with sentiment < 0 per month
                                    Only months with >= MIN_REVIEWS_THRESHOLD reviews
                                    are included in regression to remove single-review noise.

    Fitting pipeline on neg_pct (filtered):
      1. Linear regression (always)       — baseline slope + R²
      2. Polynomial degree-2 (always)     — captures acceleration / deceleration
      3. Mann-Kendall (when R² < 0.35)    — non-parametric rank test, Theil-Sen slope

    Returns (effective_slope, detail_dict).
    """
    from scipy import stats as sp
    import numpy as np
    from sqlalchemy import case as sa_case

    # ── SQL: avg_sentiment + neg_count + total per month ─────────────────
    if entity_type in ("car", "brand"):
        rows = (
            session.query(
                func.to_char(CarReview.review_date, "YYYY-MM").label("period"),
                func.avg(CarReviewNlp.sentiment_score).label("avg_sentiment"),
                func.count().label("cnt"),
                func.sum(
                    sa_case((CarReviewNlp.sentiment_score < 0, 1), else_=0)
                ).label("neg_count"),
            )
            .join(CarReviewNlp, CarReviewNlp.review_id == CarReview.id)
            .join(CarModel, CarReview.model_id == CarModel.id)
            .filter(CarModel.brand_id == entity_id, CarReview.review_date.isnot(None))
            .group_by("period")
            .order_by("period")
            .all()
        )
    else:
        rows = (
            session.query(
                func.to_char(InsuranceReview.review_date, "YYYY-MM").label("period"),
                func.avg(InsuranceReviewNlp.sentiment_score).label("avg_sentiment"),
                func.count().label("cnt"),
                func.sum(
                    sa_case((InsuranceReviewNlp.sentiment_score < 0, 1), else_=0)
                ).label("neg_count"),
            )
            .join(InsuranceReviewNlp, InsuranceReviewNlp.review_id == InsuranceReview.id)
            .filter(InsuranceReview.company_id == entity_id, InsuranceReview.review_date.isnot(None))
            .group_by("period")
            .order_by("period")
            .all()
        )

    # all_months: every month (for the raw reference chart)
    all_months = [
        {
            "period":               r.period,
            "avg_sentiment":        round(float(r.avg_sentiment), 4) if r.avg_sentiment is not None else None,
            "review_count":         int(r.cnt),
            "neg_pct":              round(int(r.neg_count) / int(r.cnt), 4) if r.cnt and r.neg_count is not None else None,
            "regression_predicted": None,
            "poly_predicted":       None,
        }
        for r in rows
    ]

    # filtered_months: only months with enough reviews (for fitting)
    filtered = [
        (r.period, round(int(r.neg_count) / int(r.cnt), 6), int(r.cnt))
        for r in rows
        if r.cnt and int(r.cnt) >= _MIN_REVIEWS_THRESHOLD and r.neg_count is not None
    ]
    months_filtered = len(all_months) - len(filtered)

    _empty = {
        "slope": 0.0, "r_squared": 0.0, "clean_r_squared": 0.0,
        "direction": "insufficient data", "method_used": "none",
        "mk_trend": None, "mk_p_value": None, "mk_significant": False,
        "poly_acceleration": 0.0, "poly_concavity": "linear",
        "min_reviews_threshold": _MIN_REVIEWS_THRESHOLD,
        "months_filtered": months_filtered,
        "time_series": all_months,
    }

    if len(filtered) < 3:
        return 0.0, _empty

    y_arr = np.array([v[1] for v in filtered])   # neg_pct values
    x_arr = np.array(range(len(y_arr)), dtype=float)
    weights = np.sqrt([v[2] for v in filtered])   # sqrt(review_count) weighting

    # ── 1. Weighted linear regression on neg_pct ─────────────────────────
    lin_slope, intercept, r_val, _, _ = sp.linregress(x_arr, y_arr)
    r_sq = float(r_val ** 2)

    # ── 2. Weighted polynomial degree-2 on neg_pct ───────────────────────
    poly_coeffs  = np.polyfit(x_arr, y_arr, 2, w=weights)
    poly_pred_f  = np.polyval(poly_coeffs, x_arr)
    acceleration = float(poly_coeffs[0])
    if acceleration < -0.0005:
        poly_concavity = "accelerating_decline"
    elif acceleration > 0.0005:
        poly_concavity = "decelerating_decline"
    else:
        poly_concavity = "linear"

    # ── 3. Mann-Kendall on neg_pct (when R² < 0.35) ──────────────────────
    method_used     = "linear"
    mk_trend        = None
    mk_p_value      = None
    mk_significant  = False
    effective_slope = float(lin_slope)

    if r_sq < 0.35 and len(y_arr) >= 4:
        try:
            import pymannkendall as mk_lib
            mk_result       = mk_lib.original_test(y_arr.tolist())
            mk_trend        = mk_result.trend
            mk_p_value      = round(float(mk_result.p), 4)
            mk_significant  = bool(mk_result.p < 0.05)
            effective_slope = float(mk_result.slope)
            method_used     = "mann_kendall"
        except ImportError:
            pass

    direction = (
        "declining_fast" if effective_slope >  0.02 else   # neg_pct rising fast = bad
        "declining"      if effective_slope >  0.005 else  # neg_pct rising = bad
        "stable"         if effective_slope >= -0.005 else "improving"
    )

    # Build lookup: period → (lin_pred, poly_pred) for filtered months only
    filtered_lookup: dict = {}
    for i, (period, _, _cnt) in enumerate(filtered):
        filtered_lookup[period] = (
            round(float(lin_slope) * i + float(intercept), 4),
            round(float(poly_pred_f[i]), 4),
        )

    # Merge regression predictions back into all_months
    time_series = []
    for m in all_months:
        lin_p, poly_p = filtered_lookup.get(m["period"], (None, None))
        time_series.append({**m, "regression_predicted": lin_p, "poly_predicted": poly_p})

    return effective_slope, {
        "slope":                 round(effective_slope, 6),
        "r_squared":             round(r_sq, 4),
        "clean_r_squared":       round(r_sq, 4),
        "direction":             direction,
        "method_used":           method_used,
        "mk_trend":              mk_trend,
        "mk_p_value":            mk_p_value,
        "mk_significant":        mk_significant,
        "poly_acceleration":     round(acceleration, 6),
        "poly_concavity":        poly_concavity,
        "min_reviews_threshold": _MIN_REVIEWS_THRESHOLD,
        "months_filtered":       months_filtered,
        "time_series":           time_series,
    }


# ---------------------------------------------------------------------------
# NLP helpers
# ---------------------------------------------------------------------------

def _get_complaint_labels(session: Session, nlp_rows) -> List[str]:
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
    from database.enums import SentimentLabel
    total = len(nlp_rows)
    if total == 0:
        return 0.0
    neg = sum(1 for r in nlp_rows if r.sentiment_label == SentimentLabel.NEGATIVE)
    return (neg / total) * 100


def _signal_strength(overall: float) -> str:
    if overall >= 65:
        return "strong"
    if overall >= 40:
        return "moderate"
    return "weak"


# ---------------------------------------------------------------------------
# Upsert helper
# ---------------------------------------------------------------------------

def _upsert_signal(session: Session, data: dict) -> bool:
    existing = (
        session.query(OpportunitySignal)
        .filter_by(entity_type=data["entity_type"], entity_id=data["entity_id"])
        .first()
    )
    if existing:
        existing_origin = (existing.score_reasoning or {}).get("data_origin")
        new_score = data.get("overall_score", 0)
        if existing_origin == "analyst" and new_score < float(existing.overall_score):
            data.update({
                "overall_score": float(existing.overall_score),
                "complaint_score": float(existing.complaint_score),
                "sentiment_drop_score": float(existing.sentiment_drop_score),
                "review_volume_score": float(existing.review_volume_score),
                "signal_strength": existing.signal_strength,
                "score_reasoning": existing.score_reasoning,
            })
            return False
        if existing_origin == "analyst":
            old = existing.score_reasoning or {}
            new = data.get("score_reasoning", {})
            for k in ("briefing_text", "why_text", "erp_module_recommendation"):
                if k in old and k not in new:
                    new[k] = old[k]
            new["data_origin"] = "computed"
            data["score_reasoning"] = new
        for k, v in data.items():
            if k != "id":
                setattr(existing, k, v)
        return False
    session.add(OpportunitySignal(**data))
    return True


# ---------------------------------------------------------------------------
# Main entry point — two-pass ML scoring
# ---------------------------------------------------------------------------

def compute_opportunity_signals(session: Session) -> List[Dict[str, Any]]:
    """
    Pass 1 — collect raw metrics for all entities (article signal, slope, review count, neg pct).
    Pass 2 — normalise within sector using scipy percentile rank → final scores.
    Pass 3 — upsert into opportunity_signals table.
    """
    from scipy import stats as sp

    logger.info("ML scoring: loading article embeddings…")
    article_data = _load_article_data(session)
    logger.info("Loaded %d embedded articles.", len(article_data))

    now = datetime.now(timezone.utc)
    raw: List[dict] = []

    # ── Pass 1 — Insurance ───────────────────────────────────────────────────
    for company in session.query(InsuranceCompany).filter(InsuranceCompany.is_active.is_(True)).all():
        total_rev = session.query(InsuranceReview).filter(InsuranceReview.company_id == company.id).count()
        nlp_rows = (
            session.query(InsuranceReviewNlp)
            .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
            .filter(InsuranceReview.company_id == company.id)
            .all()
        )
        art_raw, top_arts = _compute_article_signal_raw(company.name, "insurance", article_data)
        slope, trend_detail = _compute_trend_ml(session, company.id, "insurance")
        raw.append({
            "entity_type": "insurance", "entity_id": company.id,
            "entity_name": company.name, "region": company.region,
            "review_count": total_rev, "neg_pct": _negative_pct(nlp_rows),
            "complaint_labels": _get_complaint_labels(session, nlp_rows),
            "art_raw": art_raw, "top_articles": top_arts,
            "slope": slope, "trend_detail": trend_detail,
        })

    # ── Pass 1 — Car Brands ──────────────────────────────────────────────────
    for brand in session.query(CarBrand).filter(CarBrand.is_active.is_(True)).all():
        total_rev = (
            session.query(CarReview)
            .join(CarModel, CarReview.model_id == CarModel.id)
            .filter(CarModel.brand_id == brand.id)
            .count()
        )
        nlp_rows = (
            session.query(CarReviewNlp)
            .join(CarReview, CarReviewNlp.review_id == CarReview.id)
            .join(CarModel, CarReview.model_id == CarModel.id)
            .filter(CarModel.brand_id == brand.id)
            .all()
        )
        art_raw, top_arts = _compute_article_signal_raw(brand.name, "brand", article_data)
        slope, trend_detail = _compute_trend_ml(session, brand.id, "brand")
        raw.append({
            "entity_type": "brand", "entity_id": brand.id,
            "entity_name": brand.name, "region": brand.region,
            "review_count": total_rev, "neg_pct": _negative_pct(nlp_rows),
            "complaint_labels": _get_complaint_labels(session, nlp_rows),
            "art_raw": art_raw, "top_articles": top_arts,
            "slope": slope, "trend_detail": trend_detail,
        })

    # ── Pass 2 — Normalise by sector ─────────────────────────────────────────
    signals: List[dict] = []
    inserted = updated = 0

    for sector in ("insurance", "brand"):
        peers = [m for m in raw if m["entity_type"] == sector]
        if not peers:
            continue

        art_raws   = [p["art_raw"]      for p in peers]
        slopes     = [p["slope"]        for p in peers]
        log_revs   = [float(np.log1p(p["review_count"])) for p in peers]
        neg_pcts   = [p["neg_pct"]      for p in peers]
        sector_avg_neg = float(np.mean(neg_pcts)) if neg_pcts else 0.0

        for m in peers:
            # Dim 1: Article Signal → 0-35
            art_pct   = float(sp.percentileofscore(art_raws, m["art_raw"], kind="rank")) / 100
            art_score = float(round(art_pct * 35, 1))

            # Dim 2: Trend → 0-25 (more declining = higher score)
            trend_pct   = float(sp.percentileofscore(slopes, m["slope"], kind="rank")) / 100
            trend_score = float(round((1.0 - trend_pct) * 25, 1))

            # Dim 3: Market Presence → 0-20 (log-percentile)
            log_val    = float(np.log1p(m["review_count"]))
            pres_pct   = float(sp.percentileofscore(log_revs, log_val, kind="rank")) / 100
            pres_score = float(round(pres_pct * 20, 1))

            # Dim 4: Complaint Intensity → 0-20
            int_pct   = float(sp.percentileofscore(neg_pcts, m["neg_pct"], kind="rank")) / 100
            int_score = float(round(int_pct * 20, 1))

            overall  = float(round(art_score + trend_score + pres_score + int_score, 1))
            strength = _signal_strength(overall)

            trend_full = dict(m["trend_detail"])
            trend_full["score"]      = trend_score
            trend_full["percentile"] = round((1.0 - trend_pct) * 100, 1)

            reasoning = {
                "total": overall,
                "signal_strength": strength,
                "article_signal": {
                    "score": art_score, "max": 35,
                    "raw_signal": round(m["art_raw"], 5),
                    "percentile": round(art_pct * 100, 1),
                    "article_count": len(m["top_articles"]),
                    "top_articles": m["top_articles"],
                },
                "trend": trend_full,
                "market_presence": {
                    "score": pres_score, "max": 20,
                    "review_count": m["review_count"],
                    "log_normalized": round(log_val, 4),
                    "percentile": round(pres_pct * 100, 1),
                },
                "complaint_intensity": {
                    "score": int_score, "max": 20,
                    "negative_pct": round(m["neg_pct"], 1),
                    "percentile": round(int_pct * 100, 1),
                    "sector_avg_negative_pct": round(sector_avg_neg, 1),
                },
                # Legacy compat keys still read by existing profile endpoints
                "teamwill_fit": {
                    "score": art_score,
                    "matched_category": m["complaint_labels"][0] if m["complaint_labels"] else None,
                    "reason": f"Article signal {round(art_pct*100,0)}th percentile in sector",
                },
                "sector_context": {
                    "sector": sector,
                    "sector_avg_score": 0,
                    "sector_avg_negative_pct": round(sector_avg_neg, 1),
                    "performance_vs_sector": "above" if int_pct > 0.5 else "below",
                    "percentile": round(int_pct * 100, 1),
                },
            }

            data = {
                "entity_type": sector,
                "entity_id": m["entity_id"],
                "entity_name": m["entity_name"],
                "region": m["region"],
                "overall_score": overall,
                "complaint_score": art_score,
                "sentiment_drop_score": trend_score,
                "review_volume_score": pres_score,
                "top_complaint_types": m["complaint_labels"][:3] if m["complaint_labels"] else None,
                "score_reasoning": reasoning,
                "signal_strength": strength,
                "sector_percentile": round(art_pct * 100),
                "computed_at": now,
            }

            if _upsert_signal(session, data):
                inserted += 1
            else:
                updated += 1
            signals.append(data)
            session.flush()

    logger.info(
        "ML scoring done: %d signals (inserted=%d updated=%d)",
        len(signals), inserted, updated,
    )
    return signals
