"""scripts/load_v2_catalogs.py

Loads the two existing CSV catalogs into the new V2 tables:
  * aaTeamwill_competitors.csv     -> teamwill_competitors
  * aaTeamwill_erp_solutions.csv   -> teamwill_erp_solutions

Run AFTER `alembic upgrade head` has created the tables.

Usage:
    python -m scripts.load_v2_catalogs

This script:
  * Reads each CSV with proper quote handling
  * Parses comma-separated text fields into JSONB arrays (geographic_presence,
    primary_services, key_industries, erp_partnerships, notable_customers, etc.)
  * Coerces empty strings to NULL
  * Uses INSERT ... ON CONFLICT DO UPDATE so re-running is idempotent
  * Reports row counts before exit

The CSVs should sit in:  data/aaTeamwill_competitors.csv
                         data/aaTeamwill_erp_solutions.csv
"""
import csv
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:conservatoire@localhost:5432/automotive_intelligence",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
COMPETITORS_CSV = DATA_DIR / "aaTeamwill_competitors.csv"
ERP_CSV = DATA_DIR / "aaTeamwill_erp_solutions.csv"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def clean(value: str):
    """Empty / 'N/A' / 'null' -> None; otherwise stripped string."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"n/a", "na", "null", "none", "-"}:
        return None
    return s


def to_int(value):
    s = clean(value)
    if s is None:
        return None
    # Tolerate "50000+" -> 50000, "150+" -> 150
    s = s.replace("+", "").replace(",", "")
    try:
        return int(float(s))
    except ValueError:
        return None


def to_smallint(value):
    """For year fields, score fields. Clamp to safe smallint range."""
    n = to_int(value)
    if n is None:
        return None
    if -32768 <= n <= 32767:
        return n
    return None


def to_numeric(value):
    s = clean(value)
    if s is None:
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def to_bool(value):
    s = clean(value)
    if s is None:
        return None
    return s.lower() in {"yes", "true", "1", "y"}


def truncate(value, max_len: int):
    """Truncate string to max_len chars; preserves None."""
    s = clean(value)
    if s is None:
        return None
    return s[:max_len]


def to_array(value):
    """'a, b, c' -> ['a', 'b', 'c']; returns None if empty."""
    s = clean(value)
    if s is None:
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return parts or None


# ----------------------------------------------------------------------
# Loaders
# ----------------------------------------------------------------------
def load_competitors(session):
    if not COMPETITORS_CSV.exists():
        print(f"[ERROR] Missing file: {COMPETITORS_CSV}")
        return 0

    sql = text("""
        INSERT INTO teamwill_competitors (
            company_name, headquarters_country, headquarters_city,
            founded_year, employee_count_range, estimated_revenue_usd_millions,
            revenue_year, geographic_presence, countries_count,
            primary_services, key_industries, erp_partnerships,
            competitor_tier, overlap_with_teamwill_score, overlap_rationale,
            website_url, linkedin_followers_approx, recent_news_headline,
            publicly_traded, stock_ticker, data_origin
        ) VALUES (
            :company_name, :headquarters_country, :headquarters_city,
            :founded_year, :employee_count_range, :estimated_revenue_usd_millions,
            :revenue_year, CAST(:geographic_presence AS jsonb), :countries_count,
            CAST(:primary_services AS jsonb), CAST(:key_industries AS jsonb),
            CAST(:erp_partnerships AS jsonb),
            :competitor_tier, :overlap_with_teamwill_score, :overlap_rationale,
            :website_url, :linkedin_followers_approx, :recent_news_headline,
            :publicly_traded, :stock_ticker, 'imported'
        )
        ON CONFLICT (company_name) DO UPDATE SET
            headquarters_country = EXCLUDED.headquarters_country,
            estimated_revenue_usd_millions = EXCLUDED.estimated_revenue_usd_millions,
            geographic_presence = EXCLUDED.geographic_presence,
            erp_partnerships = EXCLUDED.erp_partnerships,
            overlap_with_teamwill_score = EXCLUDED.overlap_with_teamwill_score,
            updated_at = now();
    """)

    count = 0
    with open(COMPETITORS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            params = {
                "company_name": clean(row["company_name"]),
                "headquarters_country": clean(row["headquarters_country"]),
                "headquarters_city": clean(row["headquarters_city"]),
                "founded_year": to_smallint(row["founded_year"]),
                "employee_count_range": clean(row["employee_count_range"]),
                "estimated_revenue_usd_millions": to_numeric(row["estimated_revenue_usd_millions"]),
                "revenue_year": to_smallint(row["revenue_year"]),
                "geographic_presence": json.dumps(to_array(row["geographic_presence"]) or []),
                "countries_count": clean(row["countries_count"]),
                "primary_services": json.dumps(to_array(row["primary_services"]) or []),
                "key_industries": json.dumps(to_array(row["key_industries"]) or []),
                "erp_partnerships": json.dumps(to_array(row["erp_partnerships"]) or []),
                "competitor_tier": clean(row["competitor_tier"]),
                "overlap_with_teamwill_score": to_smallint(row["overlap_with_teamwill_score"]),
                "overlap_rationale": clean(row["overlap_rationale"]),
                "website_url": clean(row["website_url"]),
                "linkedin_followers_approx": to_int(row["linkedin_followers_approx"]),
                "recent_news_headline": clean(row["recent_news_headline"]),
                "publicly_traded": to_bool(row["publicly_traded"]),
                "stock_ticker": truncate(row["stock_ticker"], 30),
            }
            if not params["company_name"]:
                continue
            session.execute(sql, params)
            count += 1
    session.commit()
    return count


def load_erp_solutions(session):
    if not ERP_CSV.exists():
        print(f"[ERROR] Missing file: {ERP_CSV}")
        return 0

    sql = text("""
        INSERT INTO teamwill_erp_solutions (
            erp_name, vendor, vendor_country, founded_or_launched_year,
            deployment_model, target_company_size, global_market_share_percent,
            estimated_active_customers, pricing_model,
            starting_price_usd_per_user_per_month,
            key_modules, industries_strong_in,
            automotive_fit_score, insurance_fit_score,
            g2_rating, g2_review_count, gartner_peer_insights_rating,
            capterra_rating, trustradius_rating, average_rating_normalized,
            total_reviews_aggregate, top_pros, top_cons,
            typical_implementation_months, notable_customers,
            mena_africa_adoption, teamwill_relevance_score, data_origin
        ) VALUES (
            :erp_name, :vendor, :vendor_country, :founded_or_launched_year,
            :deployment_model, :target_company_size, :global_market_share_percent,
            :estimated_active_customers, :pricing_model,
            :starting_price_usd_per_user_per_month,
            CAST(:key_modules AS jsonb), CAST(:industries_strong_in AS jsonb),
            :automotive_fit_score, :insurance_fit_score,
            :g2_rating, :g2_review_count, :gartner_peer_insights_rating,
            :capterra_rating, :trustradius_rating, :average_rating_normalized,
            :total_reviews_aggregate, :top_pros, :top_cons,
            :typical_implementation_months, CAST(:notable_customers AS jsonb),
            :mena_africa_adoption, :teamwill_relevance_score, 'imported'
        )
        ON CONFLICT (erp_name) DO UPDATE SET
            vendor = EXCLUDED.vendor,
            automotive_fit_score = EXCLUDED.automotive_fit_score,
            insurance_fit_score = EXCLUDED.insurance_fit_score,
            teamwill_relevance_score = EXCLUDED.teamwill_relevance_score,
            notable_customers = EXCLUDED.notable_customers,
            updated_at = now();
    """)

    count = 0
    with open(ERP_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            params = {
                "erp_name": clean(row["erp_name"]),
                "vendor": clean(row["vendor"]),
                "vendor_country": clean(row["vendor_country"]),
                "founded_or_launched_year": to_smallint(row["founded_or_launched_year"]),
                "deployment_model": clean(row["deployment_model"]),
                "target_company_size": clean(row["target_company_size"]),
                "global_market_share_percent": clean(row["global_market_share_percent"]),
                "estimated_active_customers": to_int(row["estimated_active_customers"]),
                "pricing_model": clean(row["pricing_model"]),
                "starting_price_usd_per_user_per_month": truncate(row["starting_price_usd_per_user_per_month"], 50),
                "key_modules": json.dumps(to_array(row["key_modules"]) or []),
                "industries_strong_in": json.dumps(to_array(row["industries_strong_in"]) or []),
                "automotive_fit_score": to_smallint(row["automotive_fit_score"]),
                "insurance_fit_score": to_smallint(row["insurance_fit_score"]),
                "g2_rating": to_numeric(row["g2_rating"]),
                "g2_review_count": to_int(row["g2_review_count"]),
                "gartner_peer_insights_rating": to_numeric(row["gartner_peer_insights_rating"]),
                "capterra_rating": to_numeric(row["capterra_rating"]),
                "trustradius_rating": to_numeric(row["trustradius_rating"]),
                "average_rating_normalized": to_numeric(row["average_rating_normalized"]),
                "total_reviews_aggregate": to_int(row["total_reviews_aggregate"]),
                "top_pros": clean(row["top_pros"]),
                "top_cons": clean(row["top_cons"]),
                "typical_implementation_months": clean(row["typical_implementation_months"]),
                "notable_customers": json.dumps(to_array(row["notable_customers"]) or []),
                "mena_africa_adoption": clean(row["mena_africa_adoption"]),
                "teamwill_relevance_score": to_smallint(row["teamwill_relevance_score"]),
            }
            if not params["erp_name"]:
                continue
            session.execute(sql, params)
            count += 1
    session.commit()
    return count


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    print(f"DB URL: {DATABASE_URL}")
    print(f"Reading from: {DATA_DIR}\n")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("Loading teamwill_competitors ...")
        n1 = load_competitors(session)
        print(f"  -> {n1} rows upserted\n")

        print("Loading teamwill_erp_solutions ...")
        n2 = load_erp_solutions(session)
        print(f"  -> {n2} rows upserted\n")

        # Final sanity check
        comp_count = session.execute(
            text("SELECT COUNT(*) FROM teamwill_competitors")
        ).scalar()
        erp_count = session.execute(
            text("SELECT COUNT(*) FROM teamwill_erp_solutions")
        ).scalar()
        print(f"DB now contains:")
        print(f"  teamwill_competitors:    {comp_count} rows")
        print(f"  teamwill_erp_solutions:  {erp_count} rows")
    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
