import asyncio
import asyncpg

async def test_conn():
    try:
        conn = await asyncpg.connect(
            user="postgres",
            password="conservatoire",
            database="automotive_intelligence",
            host="localhost"
        )
        print("SUCCESS! Asyncpg connected.")
        await conn.close()
    except Exception as e:
        print(f"FAILED Asyncpg: {e}")

if __name__ == "__main__":
    asyncio.run(test_conn())
