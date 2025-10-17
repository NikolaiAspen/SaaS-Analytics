"""
Test the EXACT query used by the month-drilldown endpoint
to see if there's a difference between direct queries and the endpoint query
"""
import asyncio
from datetime import datetime
from sqlalchemy import select
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem

async def test_month_drilldown_query():
    """Replicate the exact query from app.py month-drilldown endpoint"""

    # Exact same query as app.py lines 3726-3737
    year, month_num = 2025, 9
    target_date = datetime(year, month_num, 1)  # First day of month

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print("TESTING MONTH-DRILLDOWN QUERY FOR SEPTEMBER 2025")
        print(f"Target date: {target_date}")
        print("=" * 80)

        # Exact query from app.py
        stmt = select(InvoiceLineItem, Invoice).join(
            Invoice, InvoiceLineItem.invoice_id == Invoice.id
        ).where(
            InvoiceLineItem.period_start_date <= target_date,
            InvoiceLineItem.period_end_date >= target_date
        ).order_by(Invoice.customer_name, InvoiceLineItem.name)

        result = await session.execute(stmt)
        rows = result.all()

        # Filter for ACE SJØMAT AS
        print(f"\n{'='*80}")
        print("FILTERING FOR ACE SJØMAT AS - Invoice 2010783")
        print(f"{'='*80}")

        found = False
        for line_item, invoice in rows:
            if invoice.invoice_number == "2010783":
                found = True
                print(f"\n[FOUND] Invoice: {invoice.invoice_number}")
                print(f"  Customer: {invoice.customer_name}")
                print(f"  Transaction type: {invoice.transaction_type}")
                print(f"  Product: {line_item.name}")
                print(f"  Period: {line_item.period_start_date} to {line_item.period_end_date}")
                print(f"  Item total: {line_item.item_total} kr")
                print(f"  MRR per month: {line_item.mrr_per_month} kr")

                # This is what the backend sends to template
                mrr = line_item.mrr_per_month or 0
                print(f"\n  Backend sends to template: {mrr} kr")
                print(f"  Is this 0? {mrr == 0}")
                print(f"  Is this 890? {mrr == 890}")

        if not found:
            print("\n[ERROR] Invoice 2010783 not found in query results!")

        # Also check credit note
        print(f"\n{'='*80}")
        print("CHECKING CREDIT NOTE CN-02032")
        print(f"{'='*80}")

        found_cn = False
        for line_item, invoice in rows:
            if invoice.invoice_number == "CN-02032":
                found_cn = True
                print(f"\n[FOUND] Credit Note: {invoice.invoice_number}")
                print(f"  Customer: {invoice.customer_name}")
                print(f"  Transaction type: {invoice.transaction_type}")
                print(f"  Product: {line_item.name}")
                print(f"  Item total: {line_item.item_total} kr")
                print(f"  MRR per month: {line_item.mrr_per_month} kr")

        if not found_cn:
            print("\n[ERROR] Credit note CN-02032 not found in query results!")

if __name__ == "__main__":
    asyncio.run(test_month_drilldown_query())
