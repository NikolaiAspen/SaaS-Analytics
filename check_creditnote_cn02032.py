"""
Check credit note CN-02032 to see if MRR is -890 or -899
"""
import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem

async def check_creditnote():
    """Check credit note CN-02032"""

    target_cn = "CN-02032"

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print(f"CHECKING CREDIT NOTE {target_cn}")
        print("=" * 80)

        # Get credit note invoice
        stmt = select(Invoice).where(Invoice.invoice_number == target_cn)
        result = await session.execute(stmt)
        invoice = result.scalar_one_or_none()

        if not invoice:
            print(f"\n[ERROR] Credit note {target_cn} not found!")
            return

        print(f"\nCredit Note: {invoice.invoice_number}")
        print(f"Customer: {invoice.customer_name}")
        print(f"Date: {invoice.invoice_date}")
        print(f"Type: {invoice.transaction_type}")
        print(f"Invoice ID: {invoice.id}")

        # Get ALL line items
        stmt = select(InvoiceLineItem).where(
            InvoiceLineItem.invoice_id == invoice.id
        ).order_by(InvoiceLineItem.id)

        result = await session.execute(stmt)
        line_items = result.scalars().all()

        print(f"\n{'='*80}")
        print(f"TOTAL LINE ITEMS: {len(line_items)}")
        print(f"{'='*80}")

        total_mrr = 0
        for idx, item in enumerate(line_items, 1):
            print(f"\n--- LINE ITEM {idx} ---")
            print(f"  ID: {item.id}")
            print(f"  Product: {item.name}")
            print(f"  Description: {item.description}")
            print(f"  Period: {item.period_start_date} to {item.period_end_date}")
            print(f"  Period months: {item.period_months}")
            print(f"  Item total: {item.item_total} kr")
            print(f"  MRR per month: {item.mrr_per_month} kr")
            total_mrr += item.mrr_per_month or 0

        print(f"\n{'='*80}")
        print(f"TOTAL MRR FOR CREDIT NOTE: {total_mrr} kr")
        print(f"{'='*80}")

if __name__ == "__main__":
    asyncio.run(check_creditnote())
