import os
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:conservatoire@localhost:5432/automotive_intelligence")
engine = create_engine(url, isolation_level="AUTOCOMMIT")

with engine.connect() as conn:
    # 1. Drop the schema entirely
    conn.execute(text("DROP SCHEMA public CASCADE;"))
    conn.execute(text("CREATE SCHEMA public;"))
    conn.execute(text("GRANT ALL ON SCHEMA public TO postgres;"))
    conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
    print("Dropped and recreated public schema.")

    # 2. Drop the enums IF they survived (they shouldn't normally, but just in case)
    enums = [
        "kpi_granularity", "source_type", "review_type",
        "entity_domain", "sentiment_label", "coverage_type",
        "engine_type", "price_type", "listing_condition",
        "pipeline_status", "scrape_log_status", "run_status", "task_status"
    ]
    for e in enums:
        try:
            conn.execute(text(f"DROP TYPE IF EXISTS public.{e} CASCADE;"))
            conn.execute(text(f"DROP TYPE IF EXISTS {e} CASCADE;"))
        except Exception as err:
            pass
    print("Cleaned up enum types.")
