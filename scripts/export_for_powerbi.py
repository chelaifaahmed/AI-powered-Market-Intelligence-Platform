"""
scripts/export_for_powerbi.py
─────────────────────────────
Exports all Power BI-relevant data from PostgreSQL as flat CSV files.
Each file = one pre-joined, analysis-ready table (no foreign keys to chase).

Usage:
    .venv/Scripts/python.exe scripts/export_for_powerbi.py
    .venv/Scripts/python.exe scripts/export_for_powerbi.py --out-dir exports/powerbi

Output folder: exports/powerbi/   (created if missing)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.connection import get_sync_engine
engine = get_sync_engine()

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export DB tables to CSV for Power BI")
    p.add_argument(
        "--out-dir",
        default="exports/powerbi",
        help="Output directory for CSV files (default: exports/powerbi)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Export definitions  (name → SQL)
# Each query produces a flat, human-readable CSV.
# ---------------------------------------------------------------------------

EXPORTS: dict[str, str] = {

    # ── 1. Opportunity signals (core BI table) ──────────────────────────────
    "opportunity_signals": """
        SELECT
            os.id,
            os.entity_type,
            os.entity_id,
            COALESCE(cb.name, ic.name, 'Unknown') AS entity_name,
            COALESCE(cb.country, ic.country, '')  AS entity_country,
            os.signal_strength,
            CASE
                WHEN os.signal_strength >= 65 THEN 'Strong'
                WHEN os.signal_strength >= 40 THEN 'Moderate'
                ELSE 'Weak'
            END AS signal_tier,
            os.complaint_score,
            os.sentiment_drop_score,
            os.volume_score,
            os.avg_sentiment,
            os.review_count,
            os.data_origin,
            os.analyst_score,
            os.analyst_notes,
            os.created_at,
            os.updated_at
        FROM opportunity_signals os
        LEFT JOIN car_brands       cb ON os.entity_type = 'car_brand'       AND os.entity_id = cb.id
        LEFT JOIN insurance_companies ic ON os.entity_type = 'insurance_company' AND os.entity_id = ic.id
        ORDER BY os.signal_strength DESC
    """,

    # ── 2. Car reviews (flat — brand + model + NLP joined) ──────────────────
    "car_reviews_flat": """
        SELECT
            cr.id,
            cb.name                              AS brand_name,
            cb.country                           AS brand_country,
            cm.name                              AS model_name,
            cm.year                              AS model_year,
            cr.rating,
            cr.review_date,
            cr.data_origin,
            cr.scraped_at,
            nlp.sentiment_label,
            nlp.sentiment_score,
            nlp.confidence_score,
            nlp.language,
            rs.name                              AS source_name,
            rs.base_url                          AS source_url
        FROM car_reviews cr
        LEFT JOIN car_brands    cb  ON cr.brand_id  = cb.id
        LEFT JOIN car_models    cm  ON cr.model_id  = cm.id
        LEFT JOIN car_review_nlp nlp ON cr.id       = nlp.review_id
        LEFT JOIN review_sources rs  ON cr.source_id = rs.id
        ORDER BY cr.review_date DESC NULLS LAST
    """,

    # ── 3. Insurance reviews (flat) ─────────────────────────────────────────
    "insurance_reviews_flat": """
        SELECT
            ir.id,
            ic.name                              AS company_name,
            ic.country                           AS company_country,
            ic.company_type,
            ir.rating,
            ir.review_date,
            ir.data_origin,
            ir.scraped_at,
            nlp.sentiment_label,
            nlp.sentiment_score,
            nlp.confidence_score,
            nlp.language,
            rs.name                              AS source_name
        FROM insurance_reviews ir
        LEFT JOIN insurance_companies  ic  ON ir.company_id = ic.id
        LEFT JOIN insurance_review_nlp nlp ON ir.id         = nlp.review_id
        LEFT JOIN review_sources       rs  ON ir.source_id  = rs.id
        ORDER BY ir.review_date DESC NULLS LAST
    """,

    # ── 4. Brand reputation scores (monthly KPIs) ───────────────────────────
    "brand_reputation_scores": """
        SELECT
            brs.id,
            cb.name                              AS brand_name,
            cb.country                           AS brand_country,
            brs.period_date,
            TO_CHAR(brs.period_date, 'YYYY-MM') AS year_month,
            brs.avg_sentiment,
            brs.review_count,
            brs.complaint_rate,
            brs.reputation_score,
            brs.data_origin,
            brs.computed_at
        FROM brand_reputation_scores brs
        LEFT JOIN car_brands cb ON brs.brand_id = cb.id
        ORDER BY brs.period_date DESC, brs.reputation_score DESC
    """,

    # ── 5. Sentiment trends (time-series) ───────────────────────────────────
    "sentiment_trends": """
        SELECT
            st.id,
            cb.name                              AS brand_name,
            cb.country                           AS brand_country,
            st.period_date,
            TO_CHAR(st.period_date, 'YYYY-MM')  AS year_month,
            st.positive_pct,
            st.neutral_pct,
            st.negative_pct,
            st.avg_score,
            st.review_count,
            st.data_origin
        FROM sentiment_trends st
        LEFT JOIN car_brands cb ON st.brand_id = cb.id
        ORDER BY st.period_date DESC
    """,

    # ── 6. Car listings (market supply) ─────────────────────────────────────
    "car_listings_flat": """
        SELECT
            cl.id,
            cb.name                              AS brand_name,
            cm.name                              AS model_name,
            cm.year                              AS model_year,
            cl.price,
            cl.currency,
            cl.mileage_km,
            cl.condition,
            cl.region,
            cl.country,
            cl.listing_date,
            cl.source_url,
            cl.data_origin,
            cl.scraped_at
        FROM car_listings cl
        LEFT JOIN car_brands cb ON cl.brand_id = cb.id
        LEFT JOIN car_models cm ON cl.model_id = cm.id
        ORDER BY cl.listing_date DESC NULLS LAST
    """,

    # ── 7. News articles with sentiment ─────────────────────────────────────
    "articles_flat": """
        SELECT
            a.id,
            a.title,
            a.source_name,
            a.source_url,
            a.publication_date,
            TO_CHAR(a.publication_date, 'YYYY-MM') AS year_month,
            a.language,
            a.region,
            a.sentiment_label,
            a.sentiment_score,
            a.data_origin,
            a.scraped_at
        FROM articles a
        ORDER BY a.publication_date DESC NULLS LAST
    """,

    # ── 8. Competitor pricing ────────────────────────────────────────────────
    "competitor_pricing": """
        SELECT
            cp.id,
            cb.name                              AS brand_name,
            cm.name                              AS model_name,
            cm.year                              AS model_year,
            cp.price,
            cp.currency,
            cp.price_type,
            cp.region,
            cp.country,
            cp.effective_date,
            cp.data_origin
        FROM competitor_pricing cp
        LEFT JOIN car_brands cb ON cp.brand_id = cb.id
        LEFT JOIN car_models cm ON cp.model_id = cm.id
        ORDER BY cp.effective_date DESC NULLS LAST
    """,

    # ── 9. Insurance companies reference ────────────────────────────────────
    "insurance_companies": """
        SELECT
            ic.id,
            ic.name,
            ic.country,
            ic.company_type,
            ic.website_url,
            ic.data_origin,
            COUNT(ir.id)                         AS total_reviews,
            ROUND(AVG(ir.rating)::numeric, 2)    AS avg_rating
        FROM insurance_companies ic
        LEFT JOIN insurance_reviews ir ON ir.company_id = ic.id
        GROUP BY ic.id, ic.name, ic.country, ic.company_type, ic.website_url, ic.data_origin
        ORDER BY total_reviews DESC
    """,

    # ── 10. Car brands reference ─────────────────────────────────────────────
    "car_brands": """
        SELECT
            cb.id,
            cb.name,
            cb.country,
            cb.data_origin,
            COUNT(DISTINCT cr.id)                AS total_reviews,
            COUNT(DISTINCT cl.id)                AS total_listings,
            ROUND(AVG(cr.rating)::numeric, 2)    AS avg_rating
        FROM car_brands cb
        LEFT JOIN car_reviews  cr ON cr.brand_id = cb.id
        LEFT JOIN car_listings cl ON cl.brand_id = cb.id
        GROUP BY cb.id, cb.name, cb.country, cb.data_origin
        ORDER BY total_reviews DESC
    """,

    # ── 11. Pipeline run history (operational) ───────────────────────────────
    "pipeline_runs": """
        SELECT
            id,
            task_name,
            status,
            records_scraped,
            records_stored,
            started_at,
            finished_at,
            EXTRACT(EPOCH FROM (finished_at - started_at))::int AS duration_seconds,
            error_message
        FROM pipeline_runs
        ORDER BY started_at DESC
    """,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def export_all(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'─'*55}")
    print(f"  Power BI Export  —  {timestamp}")
    print(f"  Output: {out_dir.resolve()}")
    print(f"{'─'*55}\n")

    results: list[tuple[str, int | str]] = []

    with engine.connect() as conn:
        for name, sql in EXPORTS.items():
            try:
                df = pd.read_sql(text(sql), conn)
                csv_path = out_dir / f"{name}.csv"
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")  # utf-8-sig = Excel-safe BOM
                results.append((name, len(df)))
                print(f"  ✓  {name:<35} {len(df):>6} rows  →  {csv_path.name}")
            except Exception as exc:
                results.append((name, f"ERROR: {exc}"))
                print(f"  ✗  {name:<35} FAILED: {exc}")

    # Summary manifest
    manifest_path = out_dir / "_manifest.txt"
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(f"Power BI Export — {timestamp}\n\n")
        for name, result in results:
            status = f"{result} rows" if isinstance(result, int) else result
            f.write(f"{name}: {status}\n")

    print(f"\n{'─'*55}")
    print(f"  Done. Manifest written to {manifest_path.name}")
    print(f"{'─'*55}\n")


if __name__ == "__main__":
    args = parse_args()
    export_all(Path(args.out_dir))
