"""
scripts/audit_provenance.py
-----------------------------
CLI provenance audit: prints a human-readable breakdown of data_origin
distribution across every table that has the column, then highlights
opportunity entities whose V2 scoring rests entirely on reference
(non-scraped) evidence.

Usage:
    python -m scripts.audit_provenance
    python -m scripts.audit_provenance --json        # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from database.connection import get_db_session
from sqlalchemy import text

# Tables known to carry a data_origin column (in display order)
_DOMAIN_TABLES = [
    ("car_reviews",            "Car reviews (Trustpilot)"),
    ("insurance_reviews",      "Insurance reviews (Trustpilot)"),
    ("car_listings",           "Car listings (AutoScout24)"),
    ("market_trend_articles",  "Market articles (RSS)"),
    ("competitor_pricings",    "Competitor pricings"),
    ("company_action_signals", "Company action signals"),
    ("company_tech_stack",     "Company tech stack"),
    ("erp_vendors",            "ERP vendors"),
    ("teamwill_competitors",   "Teamwill competitors"),
    ("teamwill_erp_solutions", "Teamwill ERP solutions"),
    ("company_profile",        "Company profiles"),
    ("brand_reputation_scores","Brand reputation scores"),
    ("sentiment_trends",       "Sentiment trends"),
]


def _table_distribution(session, table: str) -> dict[str, int]:
    rows = session.execute(
        text(f"SELECT data_origin, COUNT(*) FROM {table} GROUP BY data_origin ORDER BY data_origin")  # noqa: S608
    ).fetchall()
    return {(r[0] or "NULL"): int(r[1]) for r in rows}


def _opportunity_evidence_summary(session) -> list[dict]:
    """Return per-entity evidence quality from the V2 reasoning block."""
    rows = session.execute(text("""
        SELECT entity_name, entity_type, region, v2_tier,
               v2_reasoning -> 'data_quality' AS dq
        FROM opportunity_signals
        WHERE v2_reasoning IS NOT NULL
        ORDER BY entity_name
    """)).fetchall()

    result = []
    for r in rows:
        dq = r.dq or {}
        result.append({
            "entity":            r.entity_name,
            "type":              r.entity_type,
            "region":            r.region or "?",
            "v2_tier":           r.v2_tier or "—",
            "evidence_strength": dq.get("evidence_strength", "—"),
            "scraped_reviews":   dq.get("scraped_review_count", 0),
            "reference_reviews": dq.get("reference_review_count", 0),
            "scraped_actions":   dq.get("scraped_action_signal_count", 0),
            "scraped_tech":      dq.get("scraped_tech_stack_count", 0),
        })
    return result


def _print_table_report(distros: dict[str, dict[str, int]]) -> None:
    print("\n=== DATA ORIGIN DISTRIBUTION BY TABLE ===\n")
    col_w = 30
    print(f"{'Table':<{col_w}} {'scraped':>9} {'reference':>11} {'imported':>10} {'total':>8}")
    print("-" * (col_w + 42))
    grand = {"scraped": 0, "reference": 0, "imported": 0, "total": 0}
    for table, label, d in distros:
        scraped   = d.get("scraped",   0)
        reference = d.get("reference", 0)
        imported  = d.get("imported",  0)
        total     = sum(d.values())
        grand["scraped"]   += scraped
        grand["reference"] += reference
        grand["imported"]  += imported
        grand["total"]     += total
        print(f"{label:<{col_w}} {scraped:>9,} {reference:>11,} {imported:>10,} {total:>8,}")
    print("-" * (col_w + 42))
    print(f"{'TOTAL':<{col_w}} {grand['scraped']:>9,} {grand['reference']:>11,} "
          f"{grand['imported']:>10,} {grand['total']:>8,}")
    scraped_pct = grand["scraped"] / grand["total"] * 100 if grand["total"] else 0
    print(f"\n  Real scraped intelligence: {scraped_pct:.1f}% of all records")


def _print_entity_report(entities: list[dict]) -> None:
    print("\n=== OPPORTUNITY ENTITY EVIDENCE QUALITY ===\n")
    print(f"{'Entity':<30} {'Type':<10} {'Reg':<5} {'ev_strength':<12} "
          f"{'tier':<22} {'rev':>5} {'act':>5} {'tech':>5}")
    print("-" * 100)

    by_strength: dict[str, list] = {"thin": [], "low": [], "medium": [], "high": [], "—": []}
    for e in entities:
        bucket = e["evidence_strength"] if e["evidence_strength"] in by_strength else "—"
        by_strength[bucket].append(e)

    for strength in ("high", "medium", "low", "thin", "—"):
        group = by_strength[strength]
        if not group:
            continue
        for e in group:
            print(f"{e['entity']:<30} {e['type']:<10} {e['region']:<5} "
                  f"{e['evidence_strength']:<12} {e['v2_tier']:<22} "
                  f"{e['scraped_reviews']:>5} {e['scraped_actions']:>5} {e['scraped_tech']:>5}")

    print()
    counts = {s: len(by_strength[s]) for s in ("high", "medium", "low", "thin")}
    total  = sum(counts.values())
    print("  Evidence strength summary:")
    for s in ("high", "medium", "low", "thin"):
        pct = counts[s] / total * 100 if total else 0
        print(f"    {s:<8} {counts[s]:>3}  ({pct:.0f}%)")

    thin_engage = [e for e in entities
                   if e["evidence_strength"] == "thin" and e["v2_tier"] == "engage"]
    if thin_engage:
        print(f"\n  WARNING: {len(thin_engage)} entity/ies with thin evidence scored 'engage':")
        for e in thin_engage:
            print(f"    - {e['entity']} ({e['region']})")


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 provenance audit")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    with get_db_session() as session:
        distros = []
        for table, label in _DOMAIN_TABLES:
            try:
                d = _table_distribution(session, table)
            except Exception:
                d = {"error": -1}
            distros.append((table, label, d))

        entities = _opportunity_evidence_summary(session)

    if args.json:
        output = {
            "tables": {t: d for t, _, d in distros},
            "entities": entities,
        }
        print(json.dumps(output, indent=2))
        return

    _print_table_report(distros)
    _print_entity_report(entities)
    print()


if __name__ == "__main__":
    main()
