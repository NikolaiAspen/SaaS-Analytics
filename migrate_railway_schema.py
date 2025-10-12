"""
Add missing columns to Railway PostgreSQL database
Run this once to update Railway schema to match local SQLite
"""
import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def migrate():
    async with AsyncSessionLocal() as session:
        print("="*80)
        print("RAILWAY SCHEMA MIGRATION")
        print("="*80)

        migrations = []

        # 1. Add vessel columns to invoice_line_items if they don't exist
        print("\n[1] Checking invoice_line_items table...")
        try:
            await session.execute(text("""
                ALTER TABLE invoice_line_items
                ADD COLUMN IF NOT EXISTS vessel_name VARCHAR;
            """))
            migrations.append("✓ Added vessel_name to invoice_line_items")
        except Exception as e:
            migrations.append(f"✗ vessel_name: {e}")

        try:
            await session.execute(text("""
                ALTER TABLE invoice_line_items
                ADD COLUMN IF NOT EXISTS call_sign VARCHAR;
            """))
            migrations.append("✓ Added call_sign to invoice_line_items")
        except Exception as e:
            migrations.append(f"✗ call_sign: {e}")

        # 2. Add line count columns to invoice_mrr_snapshots if they don't exist
        print("\n[2] Checking invoice_mrr_snapshots table...")
        try:
            await session.execute(text("""
                ALTER TABLE invoice_mrr_snapshots
                ADD COLUMN IF NOT EXISTS active_lines INTEGER DEFAULT 0;
            """))
            migrations.append("✓ Added active_lines to invoice_mrr_snapshots")
        except Exception as e:
            migrations.append(f"✗ active_lines: {e}")

        try:
            await session.execute(text("""
                ALTER TABLE invoice_mrr_snapshots
                ADD COLUMN IF NOT EXISTS invoice_lines INTEGER DEFAULT 0;
            """))
            migrations.append("✓ Added invoice_lines to invoice_mrr_snapshots")
        except Exception as e:
            migrations.append(f"✗ invoice_lines: {e}")

        try:
            await session.execute(text("""
                ALTER TABLE invoice_mrr_snapshots
                ADD COLUMN IF NOT EXISTS creditnote_lines INTEGER DEFAULT 0;
            """))
            migrations.append("✓ Added creditnote_lines to invoice_mrr_snapshots")
        except Exception as e:
            migrations.append(f"✗ creditnote_lines: {e}")

        # 3. Create indexes for new columns
        print("\n[3] Creating indexes...")
        try:
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_invoice_line_items_vessel_name
                ON invoice_line_items(vessel_name);
            """))
            migrations.append("✓ Created index on vessel_name")
        except Exception as e:
            migrations.append(f"✗ vessel_name index: {e}")

        try:
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_invoice_line_items_call_sign
                ON invoice_line_items(call_sign);
            """))
            migrations.append("✓ Created index on call_sign")
        except Exception as e:
            migrations.append(f"✗ call_sign index: {e}")

        # Commit all changes
        await session.commit()

        print("\n" + "="*80)
        print("MIGRATION COMPLETE")
        print("="*80)
        for msg in migrations:
            print(f"  {msg}")
        print("="*80)

if __name__ == "__main__":
    asyncio.run(migrate())
