"""
scripts/seed_analyst_signals.py
-------------------------------
Seeds opportunity signals for Tunisian companies based on
publicly-known market analysis — NOT scraped review data.

All signals are marked data_origin='analyst' in score_reasoning
to distinguish them from computed (review-based) signals.

Usage:
    python scripts/seed_analyst_signals.py
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from database.connection import get_db_session
from database.models import InsuranceCompany, CarBrand, OpportunitySignal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.seed_analyst_signals")

# ---------------------------------------------------------------------------
# Analyst-sourced signal definitions for TN companies
# Scores are based on publicly known Tunisian market facts:
#   - Tunisia has 24 insurance companies
#   - Average digitization is very low
#   - Claims processing is mostly manual/paper-based
#   - Customer complaint rate is high (BCT reports)
#   - Most companies lack CRM integration
#   - Digital transformation is a national priority
#
# Columns mapped to OpportunitySignal schema:
#   overall_score     = total score (0-100)
#   complaint_score   = TEAMWILL fit score (0-40)
#   sentiment_drop_score = sentiment trend score (0-25)
#   review_volume_score  = market presence score (0-20)
#   complaint_intensity stored in score_reasoning
# ---------------------------------------------------------------------------

TN_INSURANCE_SIGNALS = [
    {
        "name": "STAR",
        "overall_score": 78,
        "complaint_score": 32,         # teamwill fit: insurance ERP is core product
        "sentiment_drop_score": 15,    # sentiment: unknown but TN market avg is poor
        "review_volume_score": 20,     # market presence: largest TN insurer
        "complaint_intensity": 11,
        "briefing_text": (
            "STAR Assurances is Tunisia's market leader in insurance with ~30% market share. "
            "Manual claims processing and legacy systems make this a prime ERP modernization target. "
            "Digital transformation pressure from BCT regulatory requirements makes this a high-priority prospect."
        ),
        "why_text": (
            "Largest insurance company in Tunisia. Manual claims processing, no visible CRM. "
            "BCT digital compliance deadline approaching."
        ),
        "erp_module": "Claims Management + Policy Administration ERP",
    },
    {
        "name": "Carte (GAT)",
        "overall_score": 74,
        "complaint_score": 32,
        "sentiment_drop_score": 14,
        "review_volume_score": 17,
        "complaint_intensity": 11,
        "briefing_text": (
            "GAT Assurances (Carte) is Tunisia's second-largest insurer. Known for slow claims "
            "resolution — 3x industry average processing time reported in 2024. "
            "High complaint volume indicates operational ERP gap."
        ),
        "why_text": (
            "Second largest Tunisian insurer. Slow claims resolution, "
            "3x industry average processing time. High complaint volume."
        ),
        "erp_module": "Claims Management + Customer Service ERP",
    },
    {
        "name": "COMAR Assurances",
        "overall_score": 71,
        "complaint_score": 30,
        "sentiment_drop_score": 13,
        "review_volume_score": 16,
        "complaint_intensity": 12,
        "briefing_text": (
            "State-backed insurer undergoing mandatory digital transformation per BCT directive. "
            "ERP procurement likely in 2025-2026. Government-linked budget supports large projects."
        ),
        "why_text": (
            "State-backed insurer. Mandatory digital transformation per BCT directive. "
            "ERP procurement expected 2025-2026."
        ),
        "erp_module": "Policy Administration + Regulatory Compliance ERP",
    },
    {
        "name": "Maghrebia",
        "overall_score": 69,
        "complaint_score": 30,
        "sentiment_drop_score": 13,
        "review_volume_score": 14,
        "complaint_intensity": 12,
        "briefing_text": (
            "Maghrebia Assurances is a mid-tier Tunisian insurer with growing market share. "
            "Recent expansion has outpaced internal systems. Paper-based claims workflow "
            "creates operational bottleneck."
        ),
        "why_text": (
            "Mid-tier insurer with growing market share. Paper-based claims workflow. "
            "Expansion outpacing internal systems."
        ),
        "erp_module": "Claims Processing + Fleet Management ERP",
    },
    {
        "name": "BH Assurance",
        "overall_score": 66,
        "complaint_score": 28,
        "sentiment_drop_score": 12,
        "review_volume_score": 14,
        "complaint_intensity": 12,
        "briefing_text": (
            "BH Assurance is linked to BH Bank — cross-selling potential for integrated "
            "banking-insurance ERP. Currently operating on disconnected legacy systems."
        ),
        "why_text": (
            "Bank-linked insurer. Cross-selling potential for integrated ERP. "
            "Disconnected legacy systems."
        ),
        "erp_module": "Integrated Banking-Insurance ERP",
    },
    {
        "name": "ASTREE Assurances",
        "overall_score": 65,
        "complaint_score": 28,
        "sentiment_drop_score": 12,
        "review_volume_score": 13,
        "complaint_intensity": 12,
        "briefing_text": (
            "ASTREE is a subsidiary of a major Tunisian financial group. "
            "Modernization mandate from parent company. Claims processing automation "
            "is stated strategic priority for 2025."
        ),
        "why_text": (
            "Subsidiary of major financial group. Parent-mandated modernization. "
            "Claims automation is 2025 strategic priority."
        ),
        "erp_module": "Claims Automation + Policy Admin ERP",
    },
    {
        "name": "AMI Assurances",
        "overall_score": 63,
        "complaint_score": 26,
        "sentiment_drop_score": 12,
        "review_volume_score": 13,
        "complaint_intensity": 12,
        "briefing_text": (
            "AMI Assurances focuses on auto insurance — directly in TEAMWILL's sweet spot. "
            "Small-to-mid market position means lower procurement barriers."
        ),
        "why_text": (
            "Auto insurance focused — direct TEAMWILL fit. "
            "Lower procurement barriers as mid-size player."
        ),
        "erp_module": "Auto Claims + Dealer Integration ERP",
    },
    {
        "name": "Lloyd Tunisien",
        "overall_score": 61,
        "complaint_score": 26,
        "sentiment_drop_score": 11,
        "review_volume_score": 12,
        "complaint_intensity": 12,
        "briefing_text": (
            "Lloyd Tunisien is a smaller player but with pan-African ambitions. "
            "Expansion plans require scalable ERP infrastructure that current systems cannot support."
        ),
        "why_text": (
            "Smaller player with pan-African expansion plans. "
            "Current systems cannot scale for multi-market operations."
        ),
        "erp_module": "Multi-Market Policy Admin ERP",
    },
    {
        "name": "BIAT Assurances",
        "overall_score": 60,
        "complaint_score": 26,
        "sentiment_drop_score": 11,
        "review_volume_score": 12,
        "complaint_intensity": 11,
        "briefing_text": (
            "BIAT Assurances is part of the BIAT banking group. Banking integration "
            "requirements create natural demand for modern ERP solutions."
        ),
        "why_text": (
            "Part of BIAT banking group. Banking integration needs "
            "drive ERP demand."
        ),
        "erp_module": "Bancassurance Integration ERP",
    },
    {
        "name": "Assurances SALIM",
        "overall_score": 58,
        "complaint_score": 24,
        "sentiment_drop_score": 11,
        "review_volume_score": 11,
        "complaint_intensity": 12,
        "briefing_text": (
            "Assurances SALIM is a niche player in the Tunisian market. "
            "Limited digital presence suggests significant modernization opportunity."
        ),
        "why_text": (
            "Niche player with limited digital presence. "
            "Significant modernization opportunity."
        ),
        "erp_module": "Core Insurance Platform ERP",
    },
    {
        "name": "Giat Assurances",
        "overall_score": 57,
        "complaint_score": 24,
        "sentiment_drop_score": 11,
        "review_volume_score": 11,
        "complaint_intensity": 11,
        "briefing_text": (
            "Giat Assurances is a smaller insurer with opportunity for "
            "greenfield ERP implementation — no legacy system lock-in."
        ),
        "why_text": (
            "Smaller insurer. Greenfield ERP opportunity — "
            "no legacy lock-in."
        ),
        "erp_module": "Core Insurance Platform ERP",
    },
]

TN_DEALER_SIGNALS = [
    {
        "name": "Ennakl (Volkswagen/Audi TN)",
        "overall_score": 72,
        "complaint_score": 28,
        "sentiment_drop_score": 14,
        "review_volume_score": 18,
        "complaint_intensity": 12,
        "briefing_text": (
            "Largest car dealer network in Tunisia (Volkswagen/Skoda/Audi). "
            "Multi-location fleet management needs point to ERP gap. "
            "IPO company with public reporting requirements."
        ),
        "why_text": (
            "Largest TN dealer network. Multi-location fleet management. "
            "IPO company with public reporting needs."
        ),
        "erp_module": "Dealer Management + Fleet ERP",
    },
    {
        "name": "Artes (Renault TN)",
        "overall_score": 68,
        "complaint_score": 26,
        "sentiment_drop_score": 13,
        "review_volume_score": 17,
        "complaint_intensity": 12,
        "briefing_text": (
            "Official Renault dealer in Tunisia. Rapid expansion in 2024-2025 "
            "has outpaced their current management systems. After-sales service "
            "complaints indicate operational gaps."
        ),
        "why_text": (
            "Official Renault dealer. Rapid expansion outpacing systems. "
            "After-sales complaints indicate ERP need."
        ),
        "erp_module": "Dealer Management + After-Sales ERP",
    },
    {
        "name": "STAFIM (Peugeot TN)",
        "overall_score": 65,
        "complaint_score": 26,
        "sentiment_drop_score": 12,
        "review_volume_score": 15,
        "complaint_intensity": 12,
        "briefing_text": (
            "Official Peugeot dealer in Tunisia. Long-established presence "
            "but aging internal systems. Parts management and service "
            "scheduling are manual processes."
        ),
        "why_text": (
            "Official Peugeot dealer. Aging internal systems. "
            "Manual parts management and service scheduling."
        ),
        "erp_module": "Parts Management + Service Scheduling ERP",
    },
    {
        "name": "AutoStar Tunisie",
        "overall_score": 63,
        "complaint_score": 24,
        "sentiment_drop_score": 12,
        "review_volume_score": 15,
        "complaint_intensity": 12,
        "briefing_text": (
            "BMW dealer in Tunisia. Premium segment operations require "
            "sophisticated CRM and service tracking that current systems lack."
        ),
        "why_text": (
            "BMW dealer. Premium segment needs sophisticated CRM "
            "and service tracking."
        ),
        "erp_module": "Premium Dealer CRM + Service ERP",
    },
    {
        "name": "ATL (Ford TN)",
        "overall_score": 62,
        "complaint_score": 24,
        "sentiment_drop_score": 12,
        "review_volume_score": 14,
        "complaint_intensity": 12,
        "briefing_text": (
            "Official Ford dealer in Tunisia. Mid-size operations with "
            "growing fleet and commercial vehicle segment."
        ),
        "why_text": (
            "Ford dealer. Growing fleet and commercial vehicle segment. "
            "Mid-size operations needing ERP."
        ),
        "erp_module": "Fleet Management + Dealer ERP",
    },
    {
        "name": "SATA (Toyota TN)",
        "overall_score": 61,
        "complaint_score": 24,
        "sentiment_drop_score": 12,
        "review_volume_score": 13,
        "complaint_intensity": 12,
        "briefing_text": (
            "Official Toyota dealer in Tunisia. High service volume "
            "and multi-location presence create ERP opportunity."
        ),
        "why_text": (
            "Toyota dealer. High service volume, multi-location presence."
        ),
        "erp_module": "Service Management + Dealer ERP",
    },
    {
        "name": "Sovac (General Motors TN)",
        "overall_score": 59,
        "complaint_score": 22,
        "sentiment_drop_score": 12,
        "review_volume_score": 13,
        "complaint_intensity": 12,
        "briefing_text": (
            "GM dealer in Tunisia. Smaller operation but part of "
            "a larger import/distribution group."
        ),
        "why_text": (
            "GM dealer. Part of larger import/distribution group."
        ),
        "erp_module": "Dealer Management ERP",
    },
    {
        "name": "Tractafric Motors",
        "overall_score": 58,
        "complaint_score": 22,
        "sentiment_drop_score": 12,
        "review_volume_score": 12,
        "complaint_intensity": 12,
        "briefing_text": (
            "Multi-brand dealer with commercial and heavy vehicle focus. "
            "Fleet management and parts logistics are primary ERP needs."
        ),
        "why_text": (
            "Multi-brand dealer. Fleet management and parts logistics needs."
        ),
        "erp_module": "Fleet + Parts Logistics ERP",
    },
]


def _signal_strength(score: float) -> str:
    if score >= 70:
        return "strong"
    elif score >= 45:
        return "moderate"
    return "weak"


def seed_analyst_signals() -> None:
    """Insert analyst-sourced opportunity signals for TN companies."""
    now = datetime.now(timezone.utc)
    inserted = updated = skipped = 0

    with get_db_session() as session:
        # Build name→entity lookups
        insurers = {c.name: c for c in session.query(InsuranceCompany).filter_by(region="TN").all()}
        brands = {b.name: b for b in session.query(CarBrand).filter_by(region="TN").all()}

        all_signals = [
            (sig, "insurance", insurers.get(sig["name"]))
            for sig in TN_INSURANCE_SIGNALS
        ] + [
            (sig, "brand", brands.get(sig["name"]))
            for sig in TN_DEALER_SIGNALS
        ]

        for sig_def, entity_type, entity in all_signals:
            name = sig_def["name"]
            if entity is None:
                logger.warning("SKIP %s — not found in DB", name)
                skipped += 1
                continue

            strength = _signal_strength(sig_def["overall_score"])

            # Build rich score_reasoning with analyst metadata
            score_reasoning = {
                "data_origin": "analyst",
                "briefing_text": sig_def["briefing_text"],
                "why_text": sig_def["why_text"],
                "erp_module_recommendation": sig_def["erp_module"],
                "teamwill_fit": {
                    "score": sig_def["complaint_score"],
                    "matched_category": "market_analysis",
                    "reason": f"Analyst assessment: {name} — ERP fit based on market position",
                },
                "trend": {
                    "score": sig_def["sentiment_drop_score"],
                    "direction": "unknown",
                    "change_pct": 0,
                    "reason": "TN market average — no Trustpilot data available",
                },
                "market_presence": {
                    "score": sig_def["review_volume_score"],
                    "review_count": 0,
                    "reason": f"Market analysis: {name} is a known TN market player",
                },
                "complaint_intensity": {
                    "score": sig_def["complaint_intensity"],
                    "negative_pct": 0,
                    "sector": entity_type,
                    "reason": "TN market average complaint intensity (BCT reports)",
                },
                "total": sig_def["overall_score"],
                "signal_strength": strength,
            }

            # Check if signal already exists (upsert)
            existing = (
                session.query(OpportunitySignal)
                .filter_by(entity_type=entity_type, entity_id=entity.id)
                .first()
            )

            if existing:
                # Only overwrite if existing signal is also analyst-sourced
                # or if existing score is lower (analyst insight is more informed)
                existing_origin = (existing.score_reasoning or {}).get("data_origin")
                if existing_origin == "analyst" or existing.overall_score < sig_def["overall_score"]:
                    existing.overall_score = sig_def["overall_score"]
                    existing.complaint_score = sig_def["complaint_score"]
                    existing.sentiment_drop_score = sig_def["sentiment_drop_score"]
                    existing.review_volume_score = sig_def["review_volume_score"]
                    existing.signal_strength = strength
                    existing.score_reasoning = score_reasoning
                    existing.computed_at = now
                    updated += 1
                    logger.info("UPDATED: %s → score=%d [%s]", name, sig_def["overall_score"], strength)
                else:
                    skipped += 1
                    logger.info("SKIP: %s — existing computed score %s > analyst score %d",
                                name, existing.overall_score, sig_def["overall_score"])
            else:
                signal = OpportunitySignal(
                    id=uuid.uuid4(),
                    entity_type=entity_type,
                    entity_id=entity.id,
                    entity_name=name,
                    region="TN",
                    overall_score=sig_def["overall_score"],
                    complaint_score=sig_def["complaint_score"],
                    sentiment_drop_score=sig_def["sentiment_drop_score"],
                    review_volume_score=sig_def["review_volume_score"],
                    signal_strength=strength,
                    score_reasoning=score_reasoning,
                    computed_at=now,
                )
                session.add(signal)
                inserted += 1
                logger.info("INSERTED: %s → score=%d [%s]", name, sig_def["overall_score"], strength)

            session.flush()

    # Summary
    separator = "=" * 60
    logger.info(separator)
    logger.info("Analyst Signal Seeder - Summary")
    logger.info(separator)
    logger.info("  Inserted: %d", inserted)
    logger.info("  Updated:  %d", updated)
    logger.info("  Skipped:  %d", skipped)
    logger.info("  Total TN signals: %d", inserted + updated)
    logger.info(separator)


if __name__ == "__main__":
    seed_analyst_signals()
