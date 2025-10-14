"""Quick check to see if Railway database has invoice data"""
import asyncio
from database import AsyncSessionLocal
from sqlalchemy import select, func
from models.invoice import Invoice, InvoiceLineItem, InvoiceMRRSnapshot

async def check():
    async with AsyncSessionLocal() as session:
        # Count invoices
        result = await session.execute(select(func.count(Invoice.id)))
        inv_count = result.scalar()

        # Count line items
        result = await session.execute(select(func.count(InvoiceLineItem.id)))
        line_count = result.scalar()

        # Count snapshots
        result = await session.execute(select(func.count(InvoiceMRRSnapshot.id)))
        snapshot_count = result.scalar()

        print("="*60)
        print("RAILWAY DATABASE STATUS CHECK")
        print("="*60)
        print(f"Invoices:        {inv_count:,}")
        print(f"Line items:      {line_count:,}")
        print(f"MRR snapshots:   {snapshot_count}")
        print("="*60)

        if inv_count > 0:
            print("✅ Railway database has invoice data!")
        else:
            print("❌ Railway database is empty")

asyncio.run(check())
