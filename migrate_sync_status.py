"""
Migration script to add new columns to sync_status table
Run this once to update the database schema
"""
import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

def safe_print(message):
    """Print with ASCII-safe characters for Windows console"""
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        # Replace Unicode characters with ASCII equivalents
        print(message.encode('ascii', errors='replace').decode('ascii'), flush=True)

async def add_column(session, column_name, column_def):
    """Add a single column in its own transaction"""
    try:
        await session.execute(text(f"ALTER TABLE sync_status ADD COLUMN {column_name} {column_def}"))
        await session.commit()
        safe_print(f"[OK] Added {column_name} column")
        return True
    except Exception as e:
        await session.rollback()
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            safe_print(f"  {column_name} column already exists")
            return True
        else:
            safe_print(f"[ERROR] Failed to add {column_name}: {e}")
            return False

async def migrate():
    """Add new columns to sync_status table"""
    safe_print("Starting migration for sync_status table...\n")

    columns_to_add = [
        ("sync_type", "VARCHAR DEFAULT 'incremental'"),
        ("invoices_synced", "INTEGER DEFAULT 0"),
        ("creditnotes_synced", "INTEGER DEFAULT 0"),
    ]

    success_count = 0
    for column_name, column_def in columns_to_add:
        async with AsyncSessionLocal() as session:
            if await add_column(session, column_name, column_def):
                success_count += 1

    safe_print(f"\n[SUCCESS] Migration completed! {success_count}/{len(columns_to_add)} columns processed.")

if __name__ == "__main__":
    asyncio.run(migrate())
