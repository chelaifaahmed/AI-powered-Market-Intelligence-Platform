import os
from sqlalchemy import create_engine, text

def reset_password():
    # Connect using the OLD working password
    db_url = "postgresql+psycopg2://postgres:Conservatoire07@localhost:5432/automotive_intelligence"
    engine = create_engine(db_url, isolation_level="AUTOCOMMIT")
    
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER USER postgres WITH PASSWORD 'conservatoire';"))
        print("\n\nSUCCESS! Password changed to 'conservatoire'.")
    except Exception as e:
        print("\n\nFAILED to change password:")
        print(e)

if __name__ == "__main__":
    reset_password()
