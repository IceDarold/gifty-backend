import asyncio
import os
from sqlalchemy import update
from app.db import SessionLocal
from app.models import TelegramSubscriber
from dotenv import load_dotenv

load_dotenv()

async def promote():
    async with SessionLocal() as session:
        stmt = update(TelegramSubscriber).values(role="superadmin")
        await session.execute(stmt)
        await session.commit()
        print("All users promoted to superadmin!")

if __name__ == "__main__":
    asyncio.run(promote())
