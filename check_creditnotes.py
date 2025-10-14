"""Check credit notes in Railway database"""
import asyncio
from database import AsyncSessionLocal
from sqlalchemy import select, func
from models.invoice import Invoice, InvoiceLineItem

async def check():
    async with AsyncSessionLocal() as session:
        # Count invoices by transaction type
        result = await session.execute(
            select(Invoice.transaction_type, func.count(Invoice.id))
            .group_by(Invoice.transaction_type)
        )
        transaction_counts = result.all()

        # Count line items by transaction type
        result = await session.execute(
            select(Invoice.transaction_type, func.count(InvoiceLineItem.id))
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .group_by(Invoice.transaction_type)
        )
        line_counts = result.all()

        # Calculate total MRR from invoices vs credit notes
        result = await session.execute(
            select(Invoice.transaction_type, func.sum(InvoiceLineItem.mrr_per_month))
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .group_by(Invoice.transaction_type)
        )
        mrr_by_type = result.all()

        print("="*60)
        print("RAILWAY DATABASE - INVOICES VS CREDIT NOTES")
        print("="*60)
        print("\nTransactions:")
        for trans_type, count in transaction_counts:
            print(f"  {trans_type:15s}: {count:,}")

        print("\nLine items:")
        for trans_type, count in line_counts:
            print(f"  {trans_type:15s}: {count:,}")

        print("\nTotal MRR contribution:")
        for trans_type, mrr in mrr_by_type:
            print(f"  {trans_type:15s}: {mrr:,.2f} NOK")

        print("="*60)

asyncio.run(check())
