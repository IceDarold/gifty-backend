import asyncio
from sqlalchemy import update
from app.db import engine
from app.models import TelegramSubscriber

async def promote():
    async with engine.begin() as conn:
        # Check if user exists first
        from sqlalchemy import select
        res = await conn.execute(select(TelegramSubscriber).where(TelegramSubscriber.chat_id == 1821014162))
        raw_user = res.scalar_one_or_none()
        
        if not raw_user:
            print("User not found in DB. Creating a dummy record...")
            from sqlalchemy import insert
            await conn.execute(insert(TelegramSubscriber).values(
                chat_id=1821014162,
                name="Artyom (Superadmin)",
                role="superadmin",
                is_active=True,
                subscriptions=["all"]
            ))
            print("User created as superadmin.")
        else:
            await conn.execute(
                update(TelegramSubscriber)
                .where(TelegramSubscriber.chat_id == 1821014162)
                .values(role="superadmin", is_active=True)
            )
            print("User promoted to superadmin.")

if __name__ == "__main__":
    asyncio.run(promote())
