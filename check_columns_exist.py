"""Check if columns exist in Railway PostgreSQL"""
import asyncio
import os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://postgres:fmjvxOqkfPbPDxegQwAaxkkgiigmEceO@shuttle.proxy.rlwy.net:36131/railway'

from sqlalchemy import text
from database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as session:
        # Try to select the columns
        try:
            result = await session.execute(text("""
                SELECT vessel_name, call_sign
                FROM invoice_line_items
                LIMIT 1
            """))
            row = result.first()
            print("SUCCESS: Columns exist!")
            print(f"  vessel_name: {row[0] if row else 'NULL'}")
            print(f"  call_sign: {row[1] if row else 'NULL'}")
        except Exception as e:
            print(f"ERROR: Columns don't exist")
            print(f"  {e}")

            # List actual columns
            result = await session.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'invoice_line_items'
                ORDER BY ordinal_position
            """))
            cols = [row[0] for row in result]
            print(f"\nActual columns in invoice_line_items:")
            for col in cols:
                print(f"  - {col}")

asyncio.run(check())
