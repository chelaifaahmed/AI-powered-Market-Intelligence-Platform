from database.connection import get_sync_engine
from sqlalchemy import text

def test_connection():
    try:
        engine = get_sync_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("\n\nSUCCESS! Database connection successful.")
    except Exception as e:
        print("\n\nCONNECTION FAILED:")
        print(str(e))

if __name__ == "__main__":
    test_connection()
