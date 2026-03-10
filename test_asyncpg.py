import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_async_connection():
    db_url = "postgresql+asyncpg://postgres:conservatoire@localhost:5432/automotive_intelligence"
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("\n\nSUCCESS: Connection works with asyncpg and 'conservatoire'!")
    except Exception as e:
        print("\n\nFAILED:")
        print(e)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_async_connection())
