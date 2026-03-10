import os
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:Conservatoire07@localhost:5432/automotive_intelligence")
engine = create_engine(url, isolation_level="AUTOCOMMIT")

enums = [
    "kpi_granularity", "source_type", "review_type",
    "entity_domain", "sentiment_label", "coverage_type",
    "engine_type", "price_type", "listing_condition",
    "pipeline_status", "scrape_log_status", "run_status", "task_status"
]

with engine.connect() as conn:
    for enum_name in enums:
        try:
            conn.execute(text(f"DROP TYPE IF EXISTS {enum_name} CASCADE"))
            print(f"Dropped {enum_name}")
        except Exception as e:
            print(f"Failed to drop {enum_name}: {e}")

    # Verify they are gone
    result = conn.execute(text("SELECT typname FROM pg_type WHERE typname IN ('task_status', 'run_status')"))
    rows = result.fetchall()
    print("Remaining test enums:", rows)
