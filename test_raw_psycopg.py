import psycopg2

try:
    conn = psycopg2.connect(
        dbname="automotive_intelligence",
        user="postgres",
        password="conservatoire",
        host="localhost",
        port="5432"
    )
    print("\n\nSUCCESS! Connected with raw psycopg2.")
    conn.close()
except Exception as e:
    import traceback
    print("\n\nFAILED:")
    traceback.print_exc()
