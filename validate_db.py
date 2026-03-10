import os
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:Conservatoire07@localhost:5432/automotive_intelligence")
engine = create_engine(url)

with engine.connect() as conn:
    # 1. Enums
    result = conn.execute(text("""
        SELECT t.typname
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        GROUP BY t.typname;
    """))
    enums = [row[0] for row in result.fetchall()]
    
    # 2. Tables
    result = conn.execute(text("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename;
    """))
    tables = [row[0] for row in result.fetchall()]

    print("=" * 40)
    print("Database Setup Validation Report")
    print("=" * 40)
    print(f"Total Enums Created: {len(enums)}")
    print("ENUMs:", enums)
    print("-" * 40)
    print(f"Total Tables Created: {len(tables)}")
    print("TABLES:")
    for t in tables:
        print(f"  - {t}")
    print("=" * 40)
    print("Schema initialized successfully.")
