import asyncio
import sys
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from sqlalchemy import text, MetaData, Table, Column, Integer
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import make_url
from pgvector.sqlalchemy import Vector
from pgvector.asyncpg import register_vector
from app.config import get_settings

async def main():
    settings = get_settings()
    db_url = make_url(str(settings.database_url))
    
    # Force asyncpg
    if db_url.drivername in {"postgresql", "postgresql+psycopg2"}:
        db_url = db_url.set(drivername="postgresql+asyncpg")

    # Manually configure engine as in app/db.py
    engine = create_async_engine(db_url, echo=True) # Echo ON to see SQL
    
    # We deliberately DO NOT register_vector to rely on SQLAlchemy string serialization.

    try:
        async with engine.connect() as conn:
            print("Inspecting constraints for 'product_embeddings'...")
            
            # Query pg_constraint
            sql = text("""
                SELECT conname, contype
                FROM pg_constraint 
                JOIN pg_class ON pg_constraint.conrelid = pg_class.oid
                WHERE pg_class.relname = 'product_embeddings'
            """)
            
            res = await conn.execute(sql)
            rows = res.fetchall()
            print("Constraints found:")
            for r in rows:
                print(f" - {r.conname} (Type: {r.contype})")
            
    except Exception as e:
        print(f"Inspection failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())

