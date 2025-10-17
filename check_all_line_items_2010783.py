"""
Check ALL line items for invoice 2010783 - there might be multiple
"""
import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem

async def check_all_items():
    """Check all line items for invoice 2010783"""

    target_invoice = "2010783"

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print(f"CHECKING ALL LINE ITEMS FOR INVOICE {target_invoice}")
        print("=" * 80)

        # Get invoice
        stmt = select(Invoice).where(Invoice.invoice_number == target_invoice)
        result = await session.execute(stmt)
        invoice = result.scalar_one_or_none()

        if not invoice:
            print(f"\n[ERROR] Invoice {target_invoice} not found!")
            return

        print(f"\nInvoice: {invoice.invoice_number}")
        print(f"Customer: {invoice.customer_name}")
        print(f"Date: {invoice.invoice_date}")
        print(f"Invoice ID: {invoice.id}")

        # Get ALL line items - no filter
        stmt = select(InvoiceLineItem).where(
            InvoiceLineItem.invoice_id == invoice.id
        ).order_by(InvoiceLineItem.id)

        result = await session.execute(stmt)
        line_items = result.scalars().all()

        print(f"\n{'='*80}")
        print(f"TOTAL LINE ITEMS: {len(line_items)}")
        print(f"{'='*80}")

        for idx, item in enumerate(line_items, 1):
            print(f"\n--- LINE ITEM {idx} ---")
            print(f"  ID: {item.id}")
            print(f"  Product: {item.name}")
            print(f"  Description: {item.description}")
            print(f"  Period: {item.period_start_date} to {item.period_end_date}")
            print(f"  Period months: {item.period_months}")
            print(f"  Item total: {item.item_total} kr")
            print(f"  MRR per month: {item.mrr_per_month} kr")
            print(f"  Vessel: {item.vessel_name}")
            print(f"  Call sign: {item.call_sign}")

if __name__ == "__main__":
    asyncio.run(check_all_items())
