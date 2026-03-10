import psycopg

try:
    with psycopg.connect(
        dbname="automotive_intelligence",
        user="postgres",
        password="conservatoire",
        host="localhost",
        port="5432"
    ) as conn:
        print("SUCCESS! Connected with psycopg3.")
except Exception as e:
    print(f"FAILED: {e}")
