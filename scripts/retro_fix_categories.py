from app.db import SessionLocal
from app.models import Product, ParsingSource
import asyncio

async def retro_fix():
    async with SessionLocal() as db:
        from sqlalchemy import select, update, and_
        
        # Find all sources that have a discovery_name
        stmt = select(ParsingSource).where(ParsingSource.config.has_key('discovery_name'))
        res = await db.execute(stmt)
        sources = res.scalars().all()
        
        print(f"Found {len(sources)} sources for retro-fix")
        
        total_fixed = 0
        for s in sources:
            cat_name = s.config.get('discovery_name')
            # Look for products for this site_key that have category=NULL
            # and potentially originated from this source_id (if we had it, but we don't always track old source_id)
            # Actually, we have source_id in raw_data sometimes, but let's just use site_key + active runs.
            
            # More reliable: find products where category IS NULL and they belong to this site_key.
            # But which source do they belong to? 
            # If a site has only ONE category source, it's easy. If it has many, it's hard.
            
            # Let's check how many products have category NULL
            stmt_null = select(Product).where(and_(Product.gift_id.like(f"{s.site_key}:%"), Product.category.is_(None)))
            res_null = await db.execute(stmt_null)
            null_products = res_null.scalars().all()
            
            if null_products:
                print(f"Updating {len(null_products)} products for site {s.site_key} to category '{cat_name}'")
                stmt_upd = update(Product).where(
                    and_(Product.gift_id.like(f"{s.site_key}:%"), Product.category.is_(None))
                ).values(category=cat_name)
                res_upd = await db.execute(stmt_upd)
                total_fixed += res_upd.rowcount
                
        await db.commit()
        print(f"Retro-fix completed. Total products updated: {total_fixed}")

if __name__ == "__main__":
    asyncio.run(retro_fix())
