"""
analytics/v2_opportunity_scorer.py
-----------------------------------
V2 four-axis opportunity scorer for TEAMWILL sales targeting.

Axes (each 0-100 or None):
  PAIN         — current customer distress / market pain
  RECOVERY     — observable leadership action (buying-mode signal)
  ERP_FIT      — how well TEAMWILL's portfolio fits this entity
  REACHABILITY — is the door open, or locked in with a competitor?

Combined via geometric mean (penalises weak axes) and gated into sales tiers:
  engage | develop | watch | needs_investigation

An evidence_strength gate runs AFTER the axis combination: entities with thin
or low scraped evidence cannot be promoted to engage (they cap at develop or
needs_investigation regardless of axis scores).

V1 (opportunity_scorer.py) is NOT modified.  V2 results live in v2_* columns.

Public API:
    V2Scorer(session).run()
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from scipy import stats as sp
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from database.models import OpportunitySignal

logger = logging.getLogger("analytics.v2_opportunity_scorer")

# ---------------------------------------------------------------------------
# Module-level constants — tune here, never inside functions
# ---------------------------------------------------------------------------

TEAMWILL_COUNTRIES = {
    "France", "Tunisia", "Morocco", "Spain", "United Kingdom",
    "Belgium", "Germany", "Portugal", "Singapore", "United States", "Italy",
}

SOFICO_KEYWORDS = [
    "captive", "leasing", "financial services", "fleet",
    "auto finance", "mobility financial", "mobility services",
    "asset finance", "consumer credit",
]

# Recovery axis: signal type weights
RECOVERY_TYPE_WEIGHTS: Dict[str, float] = {
    "leadership_change":     3.0,
    "m&a":                   2.5,
    "strategy_announcement": 1.5,
    "partnership":           1.5,
    "digital_initiative":    1.0,
}

# Recovery axis: confidence multipliers (reused for reachability too)
RECOVERY_CONF_WEIGHTS: Dict[str, float] = {
    "high":   1.0,
    "medium": 0.7,
    "low":    0.4,
}

RECOVERY_HALF_LIFE_MONTHS = 12.0  # signals lose half their weight every 12 months

# Reachability axis
BIG_COMPETITORS = {
    "Capgemini", "Capgemini SE", "EY (Ernst & Young)", "Deloitte",
    "PwC", "KPMG", "Accenture", "IBM Consulting", "Convista",
    "Inetum", "Sopra Steria", "CGI",
}

PROPRIETARY_SIGNALS = ["proprietary", "in-house", "warp", "mainframe"]

# Vendors who explicitly REJECT traditional ERP — unreachable, not just locked-in
DEEP_PROPRIETARY_MARKERS = ["warp", "workday-built", "custom-built", "in-house erp"]

FRIENDLY_VENDORS = {"SAP", "Oracle", "Microsoft Dynamics", "Sage", "Cegid", "EBP", "Odoo"}

REACHABILITY_START = 70.0
REACHABILITY_COMPETITOR_PENALTY = 25.0
REACHABILITY_PROPRIETARY_PENALTY = 15.0
DEEP_PROPRIETARY_PENALTY = 50.0         # philosophy-level lock-in (Tesla/Warp, etc.)
REACHABILITY_SOFICO_BONUS = 25.0
REACHABILITY_FRIENDLY_BONUS = 5.0

# ERP fit axis
ERP_BASE_BRAND = 50.0
ERP_BASE_INSURANCE = 50.0
ERP_BASE_OTHER = 30.0
ERP_SOFICO_BOOST = 35.0
ERP_GEO_HOME_BONUS = 10.0
ERP_GEO_MARKET_BONUS = 5.0

# Combination
NULL_SUBSTITUTE = 30.0          # stand-in when a single axis is null
GATING_FATAL_THRESHOLD = 25.0   # weakest axis below this → 'watch'
GATING_STRONG_THRESHOLD = 60.0  # axis above this counts as 'strong'
GATING_ENGAGE_WEAKEST = 40.0    # minimum weakest to qualify for 'engage'
GATING_ENGAGE_STRONG = 2        # need this many strong axes for 'engage'

SCORER_VERSION = "v2.1"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _recency_weight(signal_date: Any, today: datetime) -> float:
    """Exponential decay: half-life = RECOVERY_HALF_LIFE_MONTHS."""
    if signal_date is None:
        return 0.3
    try:
        months_old = (today.date() - signal_date).days / 30.44
    except Exception:
        return 0.3
    return 0.5 ** (months_old / RECOVERY_HALF_LIFE_MONTHS)


def _classify_evidence_strength(
    scraped_reviews: int,
    scraped_actions: int,
    scraped_tech: int,
) -> str:
    """
    Classify how much scraped evidence backs this entity's V2 score.

    Reviews are the primary evidence signal; action/tech signals from company_*
    tables default to data_origin='scraped' (server_default) so they cannot alone
    push an entity above 'low' — that would promote seeded-only entities too high.

    high:   ≥10 scraped reviews AND ≥1 scraped action AND ≥1 scraped tech
    medium: ≥3 scraped reviews
    low:    has some scraped data but fewer than 3 reviews (includes action/tech only)
    thin:   zero scraped evidence of any kind → tier forced to needs_investigation
    """
    if scraped_reviews == 0 and scraped_actions == 0 and scraped_tech == 0:
        return "thin"
    if scraped_reviews >= 10 and scraped_actions >= 1 and scraped_tech >= 1:
        return "high"
    if scraped_reviews >= 3:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# V2Scorer
# ---------------------------------------------------------------------------

class V2Scorer:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.today = datetime.now(timezone.utc)
        self._competitor_names: Optional[set] = None

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Two-pass scoring: collect raw data, normalise within sector, persist."""
        logger.info("V2 scorer starting…")

        raw = self._pass_one()
        if not raw:
            logger.warning("No opportunity_signals rows found — nothing to score.")
            return

        updated = 0
        for sector in ("insurance", "brand"):
            peers = [e for e in raw if e["entity_type"] == sector]
            if not peers:
                continue

            recovery_raws = [e["recovery_raw"] for e in peers]

            for entity in peers:
                pain        = self._compute_pain(entity, peers)
                recovery    = self._compute_recovery(entity, recovery_raws)
                erp_fit     = self._compute_erp_fit(entity)
                reachability = self._compute_reachability(entity)
                data_quality = entity["data_quality"]

                result = self._combine(pain, recovery, erp_fit, reachability, data_quality)
                self._upsert(entity, result, pain, recovery, erp_fit, reachability, data_quality)
                updated += 1

        self.session.flush()
        logger.info("V2 scorer done — %d entities scored.", updated)

    # ------------------------------------------------------------------ #
    # Pass 1 — load raw entity data (one DB round-trip block per entity)
    # ------------------------------------------------------------------ #

    def _pass_one(self) -> List[dict]:
        rows = self.session.execute(text("""
            SELECT
                id::text            AS sig_id,
                entity_type,
                entity_id::text     AS entity_id,
                entity_name,
                region,
                overall_score,
                complaint_score,
                sentiment_drop_score,
                review_volume_score,
                score_reasoning
            FROM opportunity_signals
        """)).fetchall()

        raw: List[dict] = []
        for r in rows:
            profile      = self._load_profile(r.entity_id)
            recovery_raw = self._recovery_raw_sum(r.entity_id)
            data_quality = self._compute_data_quality(r.entity_id, r.entity_type)
            raw.append({
                "sig_id":               r.sig_id,
                "entity_type":          r.entity_type,
                "entity_id":            r.entity_id,
                "entity_name":          r.entity_name,
                "region":               r.region,
                "complaint_score":      float(r.complaint_score or 0),
                "sentiment_drop_score": float(r.sentiment_drop_score or 0),
                "review_volume_score":  float(r.review_volume_score or 0),
                "score_reasoning":      r.score_reasoning or {},
                "profile":              profile,
                "recovery_raw":         recovery_raw,
                "data_quality":         data_quality,
            })
        return raw

    def _load_profile(self, entity_id: str) -> dict:
        row = self.session.execute(text("""
            SELECT sub_segment, parent_company,
                   headquarters_country, active_countries, entity_type
            FROM company_profile
            WHERE entity_id = :eid
            LIMIT 1
        """), {"eid": entity_id}).fetchone()
        if row is None:
            return {}
        return {
            "sub_segment":          row.sub_segment or "",
            "parent_company":       row.parent_company or "",
            "headquarters_country": row.headquarters_country or "",
            "active_countries":     row.active_countries or [],
            "entity_type":          row.entity_type or "",
        }

    def _recovery_raw_sum(self, entity_id: str) -> float:
        """Recency-decayed, confidence-weighted sum of action_taken signals."""
        signals = self.session.execute(text("""
            SELECT signal_type, signal_date, confidence
            FROM company_action_signals
            WHERE entity_id = :eid
              AND polarity = 'action_taken'
              AND data_origin = 'scraped'
        """), {"eid": entity_id}).fetchall()

        total = 0.0
        for s in signals:
            type_w = RECOVERY_TYPE_WEIGHTS.get(s.signal_type, 0.0)
            rec_w  = _recency_weight(s.signal_date, self.today)
            conf_w = RECOVERY_CONF_WEIGHTS.get(s.confidence or "medium", 0.4)
            total += type_w * rec_w * conf_w
        return total

    def _compute_data_quality(self, entity_id: str, entity_type: str) -> dict:
        """
        Gather scraped evidence counts for this entity and classify evidence_strength.
        Called once per entity in pass 1.
        """
        if entity_type == "brand":
            rv = self.session.execute(text("""
                SELECT
                    COALESCE(SUM(CASE WHEN cr.data_origin = 'scraped' THEN 1 ELSE 0 END), 0) AS scraped,
                    COALESCE(SUM(CASE WHEN cr.data_origin != 'scraped' THEN 1 ELSE 0 END), 0) AS reference_count
                FROM car_reviews cr
                JOIN car_models cm ON cr.model_id = cm.id
                WHERE cm.brand_id = CAST(:eid AS uuid)
            """), {"eid": entity_id}).fetchone()
        else:
            rv = self.session.execute(text("""
                SELECT
                    COALESCE(SUM(CASE WHEN data_origin = 'scraped' THEN 1 ELSE 0 END), 0) AS scraped,
                    COALESCE(SUM(CASE WHEN data_origin != 'scraped' THEN 1 ELSE 0 END), 0) AS reference_count
                FROM insurance_reviews
                WHERE company_id = CAST(:eid AS uuid)
            """), {"eid": entity_id}).fetchone()

        scraped_reviews    = int(rv.scraped          or 0) if rv else 0
        reference_reviews  = int(rv.reference_count  or 0) if rv else 0

        scraped_actions = int(self.session.execute(text("""
            SELECT COUNT(*) FROM company_action_signals
            WHERE entity_id = :eid
              AND polarity = 'action_taken'
              AND data_origin = 'scraped'
        """), {"eid": entity_id}).scalar() or 0)

        scraped_tech = int(self.session.execute(text("""
            SELECT COUNT(*) FROM company_tech_stack
            WHERE entity_id = :eid
              AND data_origin = 'scraped'
        """), {"eid": entity_id}).scalar() or 0)

        strength = _classify_evidence_strength(scraped_reviews, scraped_actions, scraped_tech)

        return {
            "has_scraped_reviews":          scraped_reviews > 0,
            "scraped_review_count":         scraped_reviews,
            "reference_review_count":       reference_reviews,
            "has_scraped_action_signals":   scraped_actions > 0,
            "scraped_action_signal_count":  scraped_actions,
            "has_scraped_tech_stack":       scraped_tech > 0,
            "scraped_tech_stack_count":     scraped_tech,
            "evidence_strength":            strength,
        }

    # ------------------------------------------------------------------ #
    # Axis: PAIN
    # ------------------------------------------------------------------ #

    def _compute_pain(self, entity: dict, sector_peers: List[dict]) -> Optional[float]:
        """
        Pain = sector-percentile of (complaint_intensity + sentiment_drop + article_signal).

        Note on V1 column naming: V1 stores the article-signal score (0-35) in
        complaint_score and the complaint-intensity score (0-20) inside
        score_reasoning.complaint_intensity.score.

        Phase 2B — scraped-only article signal: V1._load_article_data already filters
        market_trend_articles WHERE data_origin = 'scraped' before computing complaint_score.
        V2 reads V1's pre-computed value, so the scraped-only guarantee is inherited.
        """
        reasoning = entity["score_reasoning"]

        ci_block          = (reasoning.get("complaint_intensity") or {})
        complaint_intensity = float(ci_block.get("score") or 0)
        sentiment_drop    = float(entity["sentiment_drop_score"] or 0)
        article_signal    = float(entity["complaint_score"] or 0)  # V1 misnames this column

        review_volume  = float(entity["review_volume_score"] or 0)
        article_count  = int((reasoning.get("article_signal") or {}).get("article_count") or 0)
        if review_volume < 5 and article_count == 0:
            return None

        raw_pain     = (complaint_intensity + sentiment_drop + article_signal) / 80.0 * 100.0
        pain_clamped = max(0.0, min(100.0, raw_pain))

        all_raw = [
            (float(p["score_reasoning"].get("complaint_intensity", {}).get("score") or 0)
             + float(p["sentiment_drop_score"] or 0)
             + float(p["complaint_score"] or 0)) / 80.0 * 100.0
            for p in sector_peers
        ]
        return round(float(sp.percentileofscore(all_raw, pain_clamped, kind="rank")), 2)

    # ------------------------------------------------------------------ #
    # Axis: RECOVERY
    # ------------------------------------------------------------------ #

    def _compute_recovery(
        self,
        entity: dict,
        sector_recovery_raws: List[float],
    ) -> Optional[float]:
        """
        Recovery = sector-percentile of the recency-decayed weighted sum of
        scraped action_taken signals.
        """
        raw = entity["recovery_raw"]

        if raw == 0.0:
            count = self.session.execute(text("""
                SELECT COUNT(*) FROM company_action_signals
                WHERE entity_id = :eid
                  AND polarity = 'action_taken'
                  AND data_origin = 'scraped'
            """), {"eid": entity["entity_id"]}).scalar()
            if (count or 0) == 0:
                return None

        return round(float(sp.percentileofscore(sector_recovery_raws, raw, kind="rank")), 2)

    # ------------------------------------------------------------------ #
    # Axis: ERP_FIT
    # ------------------------------------------------------------------ #

    def _compute_erp_fit(self, entity: dict) -> Optional[float]:
        """
        ERP fit = baseline by entity type + Sofico keyword boost +
        sector ERP match + geographic bonus.
        """
        profile     = entity["profile"]
        entity_type = entity["entity_type"]

        sub_segment    = profile.get("sub_segment", "") or ""
        parent_company = profile.get("parent_company", "") or ""
        hq_country     = profile.get("headquarters_country", "") or ""
        active_countries = profile.get("active_countries") or []

        if not sub_segment and not parent_company and not hq_country:
            return None

        score = ERP_BASE_BRAND if entity_type == "brand" else (
            ERP_BASE_INSURANCE if entity_type == "insurance" else ERP_BASE_OTHER
        )

        combined_text = (sub_segment + " " + parent_company).lower()
        if any(kw in combined_text for kw in SOFICO_KEYWORDS):
            score += ERP_SOFICO_BOOST

        erp_row = self.session.execute(text("""
            SELECT MAX(teamwill_relevance_score) AS max_rel,
                   MAX(automotive_fit_score)     AS max_auto,
                   MAX(insurance_fit_score)      AS max_ins
            FROM teamwill_erp_solutions
            WHERE industries_strong_in::text ILIKE '%' || :seg || '%'
        """), {"seg": sub_segment[:30] if sub_segment else ""}).fetchone()

        if erp_row and erp_row.max_rel is not None:
            fit_val = float(erp_row.max_auto or 0) if entity_type == "brand" else float(erp_row.max_ins or 0)
            score += fit_val * 2.0

        if hq_country in TEAMWILL_COUNTRIES:
            score += ERP_GEO_HOME_BONUS
        elif "Morocco" in active_countries or "Tunisia" in active_countries:
            score += ERP_GEO_MARKET_BONUS

        return round(max(0.0, min(100.0, score)), 2)

    # ------------------------------------------------------------------ #
    # Axis: REACHABILITY
    # ------------------------------------------------------------------ #

    def _load_competitor_names(self) -> set:
        if self._competitor_names is None:
            rows = self.session.execute(text("""
                SELECT company_name FROM teamwill_competitors
                WHERE overlap_with_teamwill_score >= 4
            """)).fetchall()
            self._competitor_names = {r.company_name for r in rows}
        return self._competitor_names

    def _compute_reachability(self, entity: dict) -> Optional[Any]:
        """
        Reachability = 70 baseline ± penalties/bonuses from scraped tech stack.
        Returns (score, penalties, bonuses) tuple, or None if no stack data.
        """
        competitor_names = self._load_competitor_names()
        stack = self.session.execute(text("""
            SELECT vendor, evidence_excerpt, confidence, still_active
            FROM company_tech_stack
            WHERE entity_id = :eid
              AND data_origin = 'scraped'
              AND (still_active IS NULL OR still_active = TRUE)
        """), {"eid": entity["entity_id"]}).fetchall()

        if not stack:
            return None

        score: float     = REACHABILITY_START
        penalties: List[str] = []
        bonuses:   List[str] = []

        for rec in stack:
            vendor   = rec.vendor or ""
            evidence = rec.evidence_excerpt or ""
            conf     = rec.confidence or "medium"
            conf_mult = RECOVERY_CONF_WEIGHTS.get(conf, 0.4)

            vendor_lower = vendor.lower()

            # Named TEAMWILL competitor
            if vendor in competitor_names:
                delta = REACHABILITY_COMPETITOR_PENALTY * conf_mult
                score -= delta
                penalties.append(f"{vendor} -{round(delta, 1)}")

            # Tier-1 consulting firm
            if vendor in BIG_COMPETITORS:
                delta = REACHABILITY_COMPETITOR_PENALTY * conf_mult
                score -= delta
                penalties.append(f"{vendor} -{round(delta, 1)}")

            # Deep proprietary: brand-named in-house ERP (philosophy-level rejection)
            is_proprietary = "proprietary" in vendor_lower or "in-house" in vendor_lower
            is_brand_named  = any(m in vendor_lower for m in DEEP_PROPRIETARY_MARKERS)
            if is_proprietary and is_brand_named:
                delta = DEEP_PROPRIETARY_PENALTY * conf_mult
                score -= delta
                penalties.append(f"PhilosophyLockIn({vendor}) -{round(delta, 1)}")
            elif any(p in vendor_lower for p in PROPRIETARY_SIGNALS):
                delta = REACHABILITY_PROPRIETARY_PENALTY * conf_mult
                score -= delta
                penalties.append(f"Proprietary({vendor}) -{round(delta, 1)}")

            # Sofico Miles existing customer — TEAMWILL's goldmine
            if "sofico" in vendor_lower or vendor == "Sofico Miles":
                delta = REACHABILITY_SOFICO_BONUS * conf_mult
                score += delta
                bonuses.append(f"Sofico Miles +{round(delta, 1)}")

            # Friendly ERP without a big-firm implementer
            if vendor in FRIENDLY_VENDORS:
                any_competitor = any(
                    c.lower() in evidence.lower() for c in competitor_names | BIG_COMPETITORS
                )
                if not any_competitor:
                    delta = REACHABILITY_FRIENDLY_BONUS * conf_mult
                    score += delta
                    bonuses.append(f"{vendor} +{round(delta, 1)}")

        return round(max(0.0, min(100.0, score)), 2), penalties, bonuses

    # ------------------------------------------------------------------ #
    # Combination + evidence gate
    # ------------------------------------------------------------------ #

    def _combine(
        self,
        pain:               Optional[float],
        recovery:           Optional[float],
        erp_fit:            Optional[float],
        reachability_result: Any,
        data_quality:       Optional[dict] = None,
    ) -> dict:
        # Unpack reachability tuple
        if isinstance(reachability_result, tuple):
            reachability, reach_penalties, reach_bonuses = reachability_result
        else:
            reachability   = reachability_result
            reach_penalties = []
            reach_bonuses   = []

        axes  = [pain, recovery, erp_fit, reachability]
        nulls = sum(1 for x in axes if x is None)

        if nulls >= 2:
            tier = "needs_investigation"
            result = {
                "overall": None,
                "tier":    tier,
                "reason":  f"{nulls}/4 axes lack evidence",
                "weakest_axis": None,
                "strong_axes":  0,
                "pain":         pain,
                "recovery":     recovery,
                "erp_fit":      erp_fit,
                "reachability": reachability,
                "reach_penalties": reach_penalties,
                "reach_bonuses":   reach_bonuses,
                "gate_override": None,
            }
        else:
            p = pain        if pain        is not None else NULL_SUBSTITUTE
            r = recovery    if recovery    is not None else NULL_SUBSTITUTE
            f = erp_fit     if erp_fit     is not None else NULL_SUBSTITUTE
            a = reachability if reachability is not None else NULL_SUBSTITUTE

            weakest    = min(p, r, f, a)
            strong_axes = sum(1 for x in [p, r, f, a] if x >= GATING_STRONG_THRESHOLD)
            overall    = (p * r * f * a) ** 0.25

            if weakest < GATING_FATAL_THRESHOLD:
                tier = "watch"
            elif weakest >= GATING_ENGAGE_WEAKEST and strong_axes >= GATING_ENGAGE_STRONG:
                tier = "engage"
            elif strong_axes >= 1:
                tier = "develop"
            else:
                tier = "watch"

            result = {
                "overall":      round(overall, 1),
                "tier":         tier,
                "weakest_axis": weakest,
                "strong_axes":  strong_axes,
                "pain":         pain,
                "recovery":     recovery,
                "erp_fit":      erp_fit,
                "reachability": reachability,
                "reach_penalties": reach_penalties,
                "reach_bonuses":   reach_bonuses,
                "gate_override": None,
            }

        # Evidence-strength gate — applied after axis combination
        if data_quality:
            ev = data_quality.get("evidence_strength", "")
            if ev == "thin":
                result["tier"] = "needs_investigation"
                result["gate_override"] = "evidence_strength=thin overrode tier"
            elif ev == "low" and result["tier"] == "engage":
                result["tier"] = "develop"
                result["gate_override"] = "evidence_strength=low downgraded engage→develop"

        return result

    # ------------------------------------------------------------------ #
    # Persist
    # ------------------------------------------------------------------ #

    def _upsert(
        self,
        entity:              dict,
        result:              dict,
        pain:                Optional[float],
        recovery:            Optional[float],
        erp_fit:             Optional[float],
        reachability_result: Any,
        data_quality:        dict,
    ) -> None:
        if isinstance(reachability_result, tuple):
            reachability, reach_penalties, reach_bonuses = reachability_result
        else:
            reachability   = reachability_result
            reach_penalties = []
            reach_bonuses   = []

        sig = (
            self.session.query(OpportunitySignal)
            .filter_by(
                entity_type=entity["entity_type"],
                entity_id=uuid.UUID(entity["entity_id"]),
            )
            .first()
        )
        if sig is None:
            logger.warning("No OpportunitySignal found for %s", entity["entity_name"])
            return

        sig.v2_pain_score         = float(pain)         if pain         is not None else None
        sig.v2_recovery_score     = float(recovery)     if recovery     is not None else None
        sig.v2_erp_fit_score      = float(erp_fit)      if erp_fit      is not None else None
        sig.v2_reachability_score = float(reachability) if reachability is not None else None
        sig.v2_overall_score      = float(result["overall"]) if result["overall"] is not None else None
        sig.v2_tier               = result["tier"]
        sig.v2_computed_at        = self.today

        profile = entity["profile"]

        reasoning = {
            # data_quality at the top so the dashboard can read it first
            "data_quality": data_quality,
            "axes": {
                "pain": {
                    "score": pain,
                    "components": {
                        "complaint_intensity": float(
                            (entity["score_reasoning"].get("complaint_intensity") or {}).get("score") or 0
                        ),
                        "sentiment_drop":  float(entity["sentiment_drop_score"] or 0),
                        "article_signal":  float(entity["complaint_score"] or 0),
                    },
                },
                "recovery": {
                    "score":            recovery,
                    "raw_weighted_sum": float(entity["recovery_raw"]),
                },
                "erp_fit": {
                    "score":            erp_fit,
                    "sofico_keyword_hit": any(
                        kw in (
                            (profile.get("sub_segment") or "") + " " +
                            (profile.get("parent_company") or "")
                        ).lower()
                        for kw in SOFICO_KEYWORDS
                    ),
                    "geo_bonus": (
                        ERP_GEO_HOME_BONUS
                        if (profile.get("headquarters_country") or "") in TEAMWILL_COUNTRIES
                        else (
                            ERP_GEO_MARKET_BONUS
                            if "Morocco" in (profile.get("active_countries") or [])
                            or "Tunisia" in (profile.get("active_countries") or [])
                            else 0
                        )
                    ),
                    "sub_segment":          profile.get("sub_segment"),
                    "headquarters_country": profile.get("headquarters_country"),
                },
                "reachability": {
                    "score":    reachability,
                    "penalties": reach_penalties,
                    "bonuses":   reach_bonuses,
                },
            },
            "combination": {
                "weakest_axis":     result.get("weakest_axis"),
                "weakest_score":    result.get("weakest_axis"),
                "strong_axes_count": result.get("strong_axes"),
                "geometric_mean":   result.get("overall"),
                "tier":             result["tier"],
                "gate_override":    result.get("gate_override"),
            },
            "computed_at":    self.today.isoformat(),
            "scorer_version": SCORER_VERSION,
        }

        sig.v2_reasoning = reasoning
        flag_modified(sig, "v2_reasoning")
        logger.debug(
            "%s → tier=%s overall=%.1f ev=%s (pain=%.0f rec=%.0f fit=%.0f reach=%.0f)",
            entity["entity_name"],
            result["tier"],
            result["overall"] or 0,
            data_quality.get("evidence_strength", "?"),
            pain or 0,
            recovery or 0,
            erp_fit or 0,
            reachability or 0,
        )
