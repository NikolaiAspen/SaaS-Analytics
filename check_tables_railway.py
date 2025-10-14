"""Check all invoice-related tables in Railway PostgreSQL"""
import asyncio
import os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://postgres:fmjvxOqkfPbPDxegQwAaxkkgiigmEceO@shuttle.proxy.rlwy.net:36131/railway'

from sqlalchemy import text
from database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as session:
        print("="*80)
        print("CHECKING ALL INVOICE TABLES IN RAILWAY")
        print("="*80)

        # Check invoices table
        result = await session.execute(text("SELECT COUNT(*) FROM invoices"))
        invoice_count = result.scalar()
        print(f"\nInvoices table: {invoice_count} rows")

        # Check invoice_line_items table
        result = await session.execute(text("SELECT COUNT(*) FROM invoice_line_items"))
        line_item_count = result.scalar()
        print(f"Invoice_line_items table: {line_item_count} rows")

        # Check invoice_mrr_snapshots table
        result = await session.execute(text("SELECT COUNT(*) FROM invoice_mrr_snapshots"))
        snapshot_count = result.scalar()
        print(f"Invoice_mrr_snapshots table: {snapshot_count} rows")

        # Show sample invoices if they exist
        if invoice_count > 0:
            result = await session.execute(text("""
                SELECT invoice_number, invoice_date, customer_name, total
                FROM invoices
                ORDER BY invoice_date DESC
                LIMIT 5
            """))
            invoices = result.fetchall()

            print(f"\nSample invoices:")
            for inv_num, inv_date, customer, total in invoices:
                print(f"  - {inv_num}: {customer} - {total} NOK ({inv_date})")

        print("\n" + "="*80)

asyncio.run(check())
