import asyncio
from app.db import engine, Base
# Import models so they are registered in Base.metadata
import app.models 

async def init():
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")

if __name__ == "__main__":
    asyncio.run(init())
