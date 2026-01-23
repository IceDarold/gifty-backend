import asyncio
import sys
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from sqlalchemy import text
from app.db import get_session_context

async def apply_migration():
    print("Applying LLM scoring columns migration via asyncpg...")
    async with get_session_context() as session:
        # Check if column already exists
        result = await session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='products' AND column_name='llm_gift_score';
        """))
        if result.fetchone():
            print("Migration already applied (columns exist).")
            return

        print("Adding columns...")
        statements = [
            "ALTER TABLE products ADD COLUMN llm_gift_score FLOAT;",
            "ALTER TABLE products ADD COLUMN llm_gift_reasoning TEXT;",
            "ALTER TABLE products ADD COLUMN llm_scoring_model TEXT;",
            "ALTER TABLE products ADD COLUMN llm_scoring_version TEXT;",
            "ALTER TABLE products ADD COLUMN llm_scored_at TIMESTAMP WITH TIME ZONE;",
            "CREATE INDEX ix_products_llm_gift_score ON products (llm_gift_score);"
        ]
        for stmt in statements:
            print(f"Executing: {stmt}")
            await session.execute(text(stmt))
        
        # Mark alembic revision as done if needed
        # REV ID: 0005_llm_scoring. We'll just insert it into alembic_version
        print("Updating alembic_version...")
        await session.execute(text("DELETE FROM alembic_version;"))
        await session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0005_llm_scoring');"))
        
        await session.commit()
    print("Migration successful!")

if __name__ == "__main__":
    asyncio.run(apply_migration())
