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
except Exception as e:
    # Print the raw exception bytes to see the actual error from postgres
    print(repr(str(e).encode('utf-8', 'replace')))
