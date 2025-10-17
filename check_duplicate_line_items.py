"""
Check if there are MULTIPLE line items for invoice 2010783
that could explain why Railway shows 0 kr
"""
import asyncio
from datetime import datetime
from sqlalchemy import select
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem

async def check_duplicates():
    """Check for duplicate line items"""

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print("CHECKING FOR MULTIPLE LINE ITEMS FOR INVOICE 2010783")
        print("=" * 80)

        # Get invoice
        stmt = select(Invoice).where(Invoice.invoice_number == "2010783")
        result = await session.execute(stmt)
        invoice = result.scalar_one_or_none()

        if not invoice:
            print("\n[ERROR] Invoice not found!")
            return

        print(f"\nInvoice ID: {invoice.id}")

        # Get ALL line items for this invoice (no date filter)
        stmt = select(InvoiceLineItem).where(
            InvoiceLineItem.invoice_id == invoice.id
        ).order_by(InvoiceLineItem.id)

        result = await session.execute(stmt)
        all_items = result.scalars().all()

        print(f"\nTotal line items: {len(all_items)}")

        for idx, item in enumerate(all_items, 1):
            print(f"\n--- LINE ITEM {idx} ---")
            print(f"  ID: {item.id}")
            print(f"  Product: {item.name}")
            print(f"  Period: {item.period_start_date} to {item.period_end_date}")
            print(f"  MRR: {item.mrr_per_month} kr")

        # Now check what the month-drilldown query would return
        print(f"\n{'='*80}")
        print("WHAT MONTH-DRILLDOWN QUERY RETURNS (Sept 1 filter)")
        print(f"{'='*80}")

        target_date = datetime(2025, 9, 1)  # First day of month

        stmt = select(InvoiceLineItem).where(
            InvoiceLineItem.invoice_id == invoice.id,
            InvoiceLineItem.period_start_date <= target_date,
            InvoiceLineItem.period_end_date >= target_date
        ).order_by(InvoiceLineItem.id)

        result = await session.execute(stmt)
        filtered_items = result.scalars().all()

        print(f"\nFiltered items: {len(filtered_items)}")

        for idx, item in enumerate(filtered_items, 1):
            print(f"\n--- FILTERED ITEM {idx} ---")
            print(f"  ID: {item.id}")
            print(f"  Product: {item.name}")
            print(f"  Period: {item.period_start_date} to {item.period_end_date}")
            print(f"  MRR: {item.mrr_per_month} kr")
            print(f"  This is what Railway sees!")

if __name__ == "__main__":
    asyncio.run(check_duplicates())
