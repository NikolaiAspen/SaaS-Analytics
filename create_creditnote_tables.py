"""
Create credit note tables in the database
Run this script once to add the new tables
"""

import asyncio
from database import AsyncSessionLocal, engine
from models.invoice import Base, CreditNote, CreditNoteLineItem, InvoiceSyncStatus


async def create_tables():
    """Create credit note and sync status tables"""
    print("Creating credit note and sync status tables...")

    async with engine.begin() as conn:
        # Create the credit note and sync status tables
        await conn.run_sync(Base.metadata.create_all)

    print("✓ Tables created successfully!")
    print("  - credit_notes")
    print("  - credit_note_line_items")
    print("  - invoice_sync_status")


if __name__ == "__main__":
    asyncio.run(create_tables())
