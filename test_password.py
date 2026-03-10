from sqlalchemy import create_engine, text

def test_connection():
    db_url = "postgresql+psycopg2://postgres:conservatoire@localhost:5432/automotive_intelligence"
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("\n\nSUCCESS: Connection works with password 'conservatoire'.")
    except Exception as e:
        print("\n\nFAILED: Connection failed.")
        print(e)

if __name__ == "__main__":
    test_connection()
