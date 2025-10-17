"""
Check invoice 2010783 directly in Railway PostgreSQL database
"""
import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem

async def check_invoice():
    """Check invoice 2010783 details from Railway"""

    target_invoice = "2010783"

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print(f"CHECKING INVOICE {target_invoice} IN RAILWAY POSTGRESQL")
        print("=" * 80)

        # Get invoice
        stmt = select(Invoice).where(Invoice.invoice_number == target_invoice)
        result = await session.execute(stmt)
        invoice = result.scalar_one_or_none()

        if not invoice:
            print(f"\n[ERROR] Invoice {target_invoice} not found!")
            return

        print(f"\nInvoice found:")
        print(f"  Number: {invoice.invoice_number}")
        print(f"  Customer: {invoice.customer_name}")
        print(f"  Date: {invoice.invoice_date}")
        print(f"  Type: {invoice.transaction_type}")
        print(f"  ID: {invoice.id}")

        # Get line items
        stmt = select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
        result = await session.execute(stmt)
        line_items = result.scalars().all()

        print(f"\n{'='*80}")
        print(f"LINE ITEMS ({len(line_items)}):")
        print(f"{'='*80}")

        for item in line_items:
            print(f"\nProduct: {item.name}")
            print(f"  Description: {item.description}")
            print(f"  Period: {item.period_start_date} to {item.period_end_date}")
            print(f"  Period months: {item.period_months}")
            print(f"  Item total: {item.item_total} kr")
            print(f"  MRR per month: {item.mrr_per_month} kr")
            print(f"  Vessel: {item.vessel_name}")
            print(f"  Call sign: {item.call_sign}")

            # Check if MRR is correct
            if item.item_total and item.period_months:
                expected_mrr = item.item_total / item.period_months
                actual_mrr = item.mrr_per_month or 0
                if abs(expected_mrr - actual_mrr) > 0.01:
                    print(f"  [ERROR] MRR mismatch!")
                    print(f"    Expected: {expected_mrr:.2f} kr")
                    print(f"    Actual: {actual_mrr:.2f} kr")
                    print(f"    Difference: {actual_mrr - expected_mrr:.2f} kr")
                else:
                    print(f"  [OK] MRR is correct")

        print(f"\n{'='*80}")

if __name__ == "__main__":
    asyncio.run(check_invoice())
