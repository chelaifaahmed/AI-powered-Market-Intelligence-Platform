"""
analytics/intervention_brief_generator.py
------------------------------------------
Generates AI-powered sales intervention briefs for every entity in
opportunity_signals using Groq LLaMA-3.3-70B.

Each brief is personalized using the entity's real data (scores, signals,
hiring state, complaints) and cached in the intervention_brief JSONB column.

Usage:
    python analytics/intervention_brief_generator.py               # generate missing briefs
    python analytics/intervention_brief_generator.py --force       # regenerate all
    python analytics/intervention_brief_generator.py --entity "Mercedes"  # single entity
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make project root importable
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified

from database.connection import get_db_session
from database.models import OpportunitySignal
from groq import Groq

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LOG_FILE = Path(__file__).parent / "brief_generator_errors.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("brief_generator")

# ---------------------------------------------------------------------------
# Groq client — same pattern as api/main.py _call_groq()
# ---------------------------------------------------------------------------

_MODEL = "llama-3.3-70b-versatile"
_SYSTEM_PROMPT = (
    "You are a senior B2B sales strategist at TEAMWILL, a Tunisian ERP vendor "
    "specializing in automotive fleet management, insurance claims automation, "
    "and digital transformation for insurers and dealers. You write sharp, "
    "personalized sales intelligence briefs. You never use generic language. "
    "Every brief must reference the specific company's actual situation. "
    "Output ONLY valid JSON, no preamble, no markdown."
)

def _build_groq_client() -> Groq:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set. Add it to .env")
    return Groq(api_key=key)


def _build_prompt(entity: Dict[str, Any]) -> str:
    complaints = ", ".join(entity["top_complaint_types"]) if entity["top_complaint_types"] else "none recorded"
    signals_text = "\n".join(
        f"  - [{s['signal_date']}] {s['signal_type'].upper()}: {s['headline']}"
        for s in entity["recent_signals"]
    ) if entity["recent_signals"] else "  - No recent signals recorded"

    name = entity["entity_name"]
    ceo = entity["ceo_name"] or "unknown"
    ceo_date = entity["ceo_appointment_date"] or "unknown"
    ceo_ref = ceo if ceo != "unknown" else "The relevant director"

    return f"""You are writing a sales intelligence brief for a TEAMWILL sales rep about to contact {name}. TEAMWILL sells ERP modules for automotive dealers and insurance companies: Fleet & After-Sales Management, Claims Automation, Customer Service Management, Digital Transformation Suite, Advanced Analytics.

REAL DATA ABOUT THIS COMPANY:
- Sector: {entity['sector']} | Region: {entity['region'] or 'Unknown'}
- CEO: {ceo} (appointed: {ceo_date})
- Company state right now: {entity['company_state'] or 'Unknown'}
- What customers are publicly complaining about: {complaints}
- Sentiment trend: {entity['trend_direction'] or 'unknown'}
- Pain score: {entity['v2_pain_score']}/100 | Recovery score: {entity['v2_recovery_score']}/100
- ERP fit score: {entity['v2_erp_fit_score']}/100
- Reachability score: {entity['v2_reachability_score']}/100
- Recommended ERP module: {entity['erp_module'] or 'General ERP'}
- Actively hiring: {entity['is_hiring_aggressively']} — roles: {entity['key_hiring_roles'] or 'none known'}
- Evidence strength: {entity['evidence_strength'] or 'unknown'}

RECENT SIGNALS (what actually happened publicly):
{signals_text}

REASONING INSTRUCTIONS — follow these steps before writing:
Step 1: What is the REAL operational problem behind the complaints?
  - "Engine Issues" complaints = dealer after-sales teams overwhelmed by warranty repairs and service scheduling -> coordination and workflow breakdown
  - "Battery Issues" = EV service complexity, parts tracking, technician certification management
  - "Customer Service" complaints = claims or support queue overload, response time failures, CRM gaps
  - "Policy Pricing" = underwriting data fragmentation, pricing tool gaps
  Do NOT say "engine issues = need ERP." Say what the ENGINE ISSUES cause operationally that an ERP can fix.

Step 2: Who specifically should be contacted at {name}?
  - If CEO was appointed recently (< 18 months): contact CEO directly — new leaders are open to new systems
  - If hiring Customer Service roles: contact VP Customer Experience or COO
  - If hiring Software/Digital roles: contact CTO or CDO
  - If complaints are after-sales/engine: contact VP After-Sales or Service Director
  - If insurance claims complaints: contact Chief Claims Officer or COO
  Use the CEO name if known: {ceo}

Step 3: What is the SPECIFIC window of opportunity?
  Use the recent signals dates and company state to explain WHY NOW specifically.

Now write the JSON brief. Every field must:
- Reference {name} by name (not "the company" or "they")
- Name the specific role to contact (not "decision maker" or "management")
- Connect the specific complaint type to a specific operational failure
- Never use the words: streamline, efficiency, leverage, solution, opportunity, offer, present

Output ONLY this JSON, no preamble:
{{
  "entry_strategy": "2 sentences max. Name the specific person/role to contact at {name} and WHY based on their actual signals. Example good format: '{ceo_ref} at {name} is managing [specific operational problem from complaints]. Reach out now because [specific recent signal from the signals list].'",
  "positioning": "One sharp phrase. Must name the specific module AND the specific pain it fixes. Good: 'After-sales coordination system for a dealer network under recall pressure'. Bad: 'Integrated ERP Suite to streamline operations'",
  "outreach_tone": "One sentence. Based on {entity['company_state'] or 'Unknown'} — what psychological state is the contact in, and how should the rep sound?",
  "best_timing": "Specific. Use signal dates and company state. Example: 'Contact within 10 days — new CEO {ceo} started {ceo_date} and is still setting vendor priorities'",
  "avoid": "What specific language or approach will kill this deal for {name} specifically. Reference their actual situation.",
  "pain_escalation_days": null,
  "pain_escalation_label": "short label based on trend and pain score",
  "confidence_note": "One sentence about evidence quality for {name} specifically — mention what data sources exist.",
  "suggested_entry_message": "3 sentences. Must: 1) reference a specific public signal or complaint pattern at {name}, 2) name the operational consequence (not the symptom), 3) propose a specific micro-audit or observation — never a product pitch. Sound like a smart consultant, not a salesperson. Do NOT mention TEAMWILL by name in this message."
}}"""


def _call_groq_for_brief(entity: Dict[str, Any], client: Groq) -> Dict[str, Any]:
    # Call Groq, parse JSON, return dict. Raises on unrecoverable error.
    prompt = _build_prompt(entity)
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        top_p=0.90,
        max_tokens=1200,
    )
    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if model wrapped output
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    return json.loads(raw)


def _load_entities(session, entity_filter: Optional[str], force: bool) -> List[Dict[str, Any]]:
    """Fetch all relevant entity rows with joined data."""
    rows = session.execute(text("""
        SELECT
            os.id,
            os.entity_name,
            os.entity_type,
            os.entity_id,
            os.v2_overall_score,
            os.v2_tier,
            os.v2_pain_score,
            os.v2_recovery_score,
            os.v2_reachability_score,
            os.v2_erp_fit_score,
            os.company_state,
            os.intervention_level,
            os.ceo_name,
            os.ceo_appointment_date::text AS ceo_appointment_date,
            os.is_hiring_aggressively,
            os.key_hiring_roles,
            os.top_complaint_types,
            os.overall_score,
            os.intervention_brief,
            COALESCE(
                os.trend_direction,
                os.score_reasoning->'trend'->>'direction'
            ) AS trend_direction,
            os.v2_reasoning,
            -- erp_module from whichever entity table matches
            COALESCE(cb.erp_module, ic.erp_module) AS erp_module,
            COALESCE(cb.region, ic.region)          AS region
        FROM opportunity_signals os
        LEFT JOIN car_brands       cb ON cb.id = os.entity_id AND os.entity_type = 'brand'
        LEFT JOIN insurance_companies ic ON ic.id = os.entity_id AND os.entity_type = 'insurance'
        ORDER BY COALESCE(os.v2_overall_score, os.overall_score) DESC NULLS LAST
    """)).fetchall()

    entities = []
    for r in rows:
        if entity_filter and r.entity_name.lower() != entity_filter.lower():
            continue
        if not force and r.intervention_brief is not None:
            continue  # already generated, skip

        dq = (r.v2_reasoning or {}).get("data_quality") or {}
        entities.append({
            "id": str(r.id),
            "entity_name": r.entity_name,
            "entity_type": r.entity_type,
            "sector": "Automotive" if r.entity_type == "brand" else "Insurance",
            "region": r.region,
            "v2_overall_score": float(r.v2_overall_score or r.overall_score or 0),
            "v2_tier": r.v2_tier,
            "v2_pain_score": float(r.v2_pain_score or 0),
            "v2_recovery_score": float(r.v2_recovery_score or 0),
            "v2_reachability_score": float(r.v2_reachability_score or 0),
            "v2_erp_fit_score": float(r.v2_erp_fit_score or 0),
            "company_state": r.company_state,
            "intervention_level": r.intervention_level,
            "ceo_name": r.ceo_name,
            "ceo_appointment_date": r.ceo_appointment_date,
            "is_hiring_aggressively": bool(r.is_hiring_aggressively),
            "key_hiring_roles": r.key_hiring_roles,
            "top_complaint_types": list(r.top_complaint_types or []),
            "trend_direction": r.trend_direction,
            "erp_module": r.erp_module,
            "evidence_strength": dq.get("evidence_strength"),
            "recent_signals": [],  # filled below per entity
        })
    return entities


def _fetch_recent_signals(session, entity_id: str) -> List[Dict[str, str]]:
    rows = session.execute(text("""
        SELECT signal_type, headline, signal_date::text AS signal_date
        FROM company_action_signals
        WHERE entity_id::text = :eid
        ORDER BY signal_date DESC NULLS LAST
        LIMIT 3
    """), {"eid": entity_id}).fetchall()
    return [
        {"signal_type": r.signal_type or "", "headline": r.headline or "", "signal_date": r.signal_date or ""}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Main runner (synchronous — matches project's get_db_session pattern)
# ---------------------------------------------------------------------------

def run_generator(force: bool = False, entity_filter: Optional[str] = None) -> None:
    client = _build_groq_client()
    generated = 0
    failed = 0
    skipped = 0
    checkpoint_count = 0

    with get_db_session() as session:
        entities = _load_entities(session, entity_filter, force)

        total = len(entities)
        if total == 0:
            print("Nothing to generate. Use --force to regenerate existing briefs.")
            return

        print(f"\n{'-'*60}")
        print(f"  Generating {total} intervention briefs")
        print(f"  Model: {_MODEL}  |  Delay: 2.5s between calls")
        print(f"{'-'*60}\n")

        for i, entity in enumerate(entities, 1):
            name  = entity["entity_name"]
            score = entity["v2_overall_score"]
            level = entity["intervention_level"] or "-"

            # Fetch recent signals inside the same session
            entity["recent_signals"] = _fetch_recent_signals(session, entity["id"])

            try:
                brief = _call_groq_for_brief(entity, client)
                brief["_generated_at"] = datetime.now(timezone.utc).isoformat()

            except Exception as exc:
                # 429 rate-limit: wait 60s and retry once
                if "429" in str(exc) or "rate" in str(exc).lower():
                    logger.warning("Rate limited — waiting 60s before retry for %s", name)
                    time.sleep(60)
                    try:
                        brief = _call_groq_for_brief(entity, client)
                        brief["_generated_at"] = datetime.now(timezone.utc).isoformat()
                    except Exception as retry_exc:
                        logger.error("Retry failed for %s: %s", name, retry_exc)
                        brief = {"error": "rate_limit_retry_failed", "raw": str(retry_exc)[:500]}
                        failed += 1
                elif isinstance(exc, json.JSONDecodeError):
                    raw_text = str(exc.doc)[:500] if hasattr(exc, "doc") else str(exc)[:500]
                    logger.error("JSON parse failed for %s: %s", name, exc)
                    brief = {"error": "parse_failed", "raw": raw_text}
                    failed += 1
                else:
                    logger.error("Groq call failed for %s: %s", name, exc)
                    brief = {"error": "groq_error", "raw": str(exc)[:500]}
                    failed += 1

            # Write to DB — must flag_modified so SQLAlchemy tracks JSONB mutation
            sig = session.query(OpportunitySignal).filter_by(id=entity["id"]).first()
            if sig:
                sig.intervention_brief = brief
                flag_modified(sig, "intervention_brief")
                session.flush()

            status = "✓" if "error" not in brief else "✗"
            print(f"  {status} [{i:>3}/{total}]  {name:<35}  {level:<25}  {score:.1f}")

            generated += 1
            checkpoint_count += 1

            # Commit checkpoint every 10 entities
            if checkpoint_count >= 10:
                session.commit()
                checkpoint_count = 0
                logger.info("Checkpoint commit after %d entities", i)

            # Rate limit guard — 2.5s between calls (Groq free tier: 30 RPM)
            if i < total:
                time.sleep(2.5)

        # Final commit
        session.commit()

    real_gen = generated - failed
    print(f"\n{'-'*60}")
    print(f"  Done - {real_gen} generated, {failed} failed, {skipped} skipped")
    print(f"  Errors logged to: {_LOG_FILE}")
    print(f"{'-'*60}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate AI intervention briefs for all companies in opportunity_signals."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate briefs even for entities that already have one.",
    )
    parser.add_argument(
        "--entity", type=str, default=None, metavar="NAME",
        help="Run for a single entity by name (case-insensitive). E.g. --entity 'Mercedes'",
    )
    args = parser.parse_args()
    run_generator(force=args.force, entity_filter=args.entity)
