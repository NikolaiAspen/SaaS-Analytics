"""Force add missing columns to Railway - no IF NOT EXISTS"""
import asyncio
import os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://postgres:fmjvxOqkfPbPDxegQwAaxkkgiigmEceO@shuttle.proxy.rlwy.net:36131/railway'

from sqlalchemy import text
from database import AsyncSessionLocal

async def add_columns():
    async with AsyncSessionLocal() as session:
        print("="*60)
        print("FORCE ADDING COLUMNS TO RAILWAY")
        print("="*60)

        try:
            # Add vessel_name
            await session.execute(text("ALTER TABLE invoice_line_items ADD COLUMN vessel_name VARCHAR"))
            print("[1] Added vessel_name to invoice_line_items")
        except Exception as e:
            print(f"[1] vessel_name: {e}")

        try:
            # Add call_sign
            await session.execute(text("ALTER TABLE invoice_line_items ADD COLUMN call_sign VARCHAR"))
            print("[2] Added call_sign to invoice_line_items")
        except Exception as e:
            print(f"[2] call_sign: {e}")

        try:
            # Add active_lines
            await session.execute(text("ALTER TABLE invoice_mrr_snapshots ADD COLUMN active_lines INTEGER DEFAULT 0"))
            print("[3] Added active_lines to invoice_mrr_snapshots")
        except Exception as e:
            print(f"[3] active_lines: {e}")

        try:
            # Add invoice_lines
            await session.execute(text("ALTER TABLE invoice_mrr_snapshots ADD COLUMN invoice_lines INTEGER DEFAULT 0"))
            print("[4] Added invoice_lines to invoice_mrr_snapshots")
        except Exception as e:
            print(f"[4] invoice_lines: {e}")

        try:
            # Add creditnote_lines
            await session.execute(text("ALTER TABLE invoice_mrr_snapshots ADD COLUMN creditnote_lines INTEGER DEFAULT 0"))
            print("[5] Added creditnote_lines to invoice_mrr_snapshots")
        except Exception as e:
            print(f"[5] creditnote_lines: {e}")

        # Commit
        await session.commit()
        print("\n[OK] COMMIT successful")
        print("="*60)

asyncio.run(add_columns())
