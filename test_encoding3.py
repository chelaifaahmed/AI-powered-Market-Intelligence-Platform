import psycopg2

try:
    conn = psycopg2.connect(
        dbname="automotive_intelligence",
        user="postgres",
        password="conservatoire",
        host="localhost",
        port="5432"
    )
    print("SUCCESS")
    conn.close()
except psycopg2.OperationalError as e:
    raw_error = str(e).encode('latin1', errors='ignore')
    print("Postgres raw error:", raw_error)
except Exception as e:
    print("Other error:", e)
