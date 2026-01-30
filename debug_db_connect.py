import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Сюда мы подставим строку из .env на Render
# DATABASE_URL="postgresql://postgres.gcstdfuwypoiheusgdzh:WhpW%Z2r%&2b8&R@aws-1-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require"

# Парсим URL, имитируя логику app/db.py
DB_URL_RAW = "postgresql+asyncpg://postgres.gcstdfuwypoiheusgdzh:WhpW%Z2r%&2b8&R@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

import ssl

# Настройка SSL как в продакшене
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

connect_args = {
    "ssl": ssl_context,
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0
}

async def check_connection():
    print(f"Connecting to: {DB_URL_RAW.split('@')[1]}") # Скрываем пароль
    print(f"Connect Args: {connect_args}")
    
    engine = create_async_engine(
        DB_URL_RAW,
        echo=True,
        connect_args=connect_args
    )
    
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("✅ SUCCESSS! Connection established.")
            print(f"Result: {result.scalar()}")
    except Exception as e:
        print("❌ FAIL! Connection failed.")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_connection())
