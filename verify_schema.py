"""Verify the database schema was created correctly."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="automotive_intelligence",
    user="postgres",
    password="conservatoire",
)
cur = conn.cursor()

# 1. Get all tables
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    ORDER BY table_name;
""")
tables = [row[0] for row in cur.fetchall()]
print(f"\n=== TABLES CREATED ({len(tables)}) ===")
for t in tables:
    print(f"  - {t}")

# 2. Get all ENUM types
cur.execute("""
    SELECT typname
    FROM pg_type
    WHERE typtype = 'e'
    ORDER BY typname;
""")
enums = [row[0] for row in cur.fetchall()]
print(f"\n=== ENUM TYPES ({len(enums)}) ===")
for e in enums:
    print(f"  - {e}")

# 3. Check alembic_version
cur.execute("SELECT version_num FROM alembic_version;")
version = cur.fetchone()
print(f"\n=== ALEMBIC VERSION ===")
print(f"  version_num: {version[0] if version else 'N/A'}")

# 4. Key domain tables
key_tables = [
    "car_brands", "car_models", "car_listings", "car_price_history", "car_reviews",
    "insurance_companies", "insurance_policies", "insurance_quote_history", "insurance_reviews",
    "scraping_tasks", "scraping_runs", "kpi_metrics"
]
print(f"\n=== KEY DOMAIN TABLES ===")
for kt in key_tables:
    status = "EXISTS" if kt in tables else "MISSING"
    print(f"  [{status}] {kt}")

cur.close()
conn.close()
print("\nVerification complete.")
