"""Quick check of import status"""
import asyncio
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem, InvoiceSyncStatus, InvoiceMRRSnapshot
from sqlalchemy import select, func, desc

async def check_status():
    async with AsyncSessionLocal() as session:
        # Count invoices
        stmt = select(func.count(Invoice.id))
        result = await session.execute(stmt)
        invoice_count = result.scalar()

        # Count line items
        stmt = select(func.count(InvoiceLineItem.id))
        result = await session.execute(stmt)
        line_count = result.scalar()

        # Check sync status
        stmt = select(InvoiceSyncStatus).order_by(desc(InvoiceSyncStatus.created_at)).limit(1)
        result = await session.execute(stmt)
        sync = result.scalar_one_or_none()

        # Check snapshots
        stmt = select(func.count(InvoiceMRRSnapshot.id))
        result = await session.execute(stmt)
        snapshot_count = result.scalar()

        print("="*60)
        print("IMPORT STATUS")
        print("="*60)
        print(f"Invoices in database: {invoice_count:,}")
        print(f"Line items in database: {line_count:,}")
        print(f"MRR snapshots generated: {snapshot_count}")

        if sync:
            print(f"\nLast sync cutoff: {sync.last_sync_time}")
            print(f"  Invoices synced: {sync.invoices_synced:,}")
            print(f"  Credit notes synced: {sync.creditnotes_synced:,}")
            print(f"  Success: {sync.success}")

            if sync.invoices_synced == invoice_count:
                print("\n✅ IMPORT COMPLETE!")
            else:
                print("\n⏳ Import may still be in progress...")
        else:
            print("\n⚠️ No sync status found - import may not be complete")

        print("="*60)

if __name__ == "__main__":
    asyncio.run(check_status())
