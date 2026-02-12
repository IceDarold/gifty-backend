import asyncio
import os
from sqlalchemy import select
from app.db import SessionLocal

from app.models import TelegramSubscriber
from dotenv import load_dotenv

load_dotenv()

async def check():
    async with SessionLocal() as session:

        stmt = select(TelegramSubscriber)
        result = await session.execute(stmt)
        subs = result.scalars().all()
        print(f"Total subscribers: {len(subs)}")
        for s in subs:
            print(f"ID: {s.chat_id}, Name: {s.name}, Role: {s.role}")

if __name__ == "__main__":
    asyncio.run(check())
