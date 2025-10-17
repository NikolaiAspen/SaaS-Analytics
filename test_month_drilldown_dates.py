"""
Test if month-drilldown date filtering is causing invoice 2010783 to not appear
Compare first-day-of-month vs month-end snapshot approach
"""
import asyncio
from datetime import datetime
from sqlalchemy import select, and_
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem

async def test_date_filtering():
    """Compare invoice results using different date filtering approaches"""

    target_invoice = "2010783"

    # September 2025 - two different approaches
    sept_first_day = datetime(2025, 9, 1)  # Current approach in app.py
    sept_last_day = datetime(2025, 9, 30, 23, 59, 59)  # Month-end snapshot approach

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print("TESTING DATE FILTERING FOR INVOICE 2010783")
        print("=" * 80)

        # Get invoice details first
        stmt = select(Invoice).where(Invoice.invoice_number == target_invoice)
        result = await session.execute(stmt)
        invoice = result.scalar_one_or_none()

        if invoice:
            print(f"\nInvoice found: {invoice.invoice_number}")
            print(f"Customer: {invoice.customer_name}")
            print(f"Invoice date: {invoice.invoice_date}")

            # Get line items
            stmt = select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
            result = await session.execute(stmt)
            line_items = result.scalars().all()

            print(f"\nLine items: {len(line_items)}")
            for item in line_items:
                print(f"  - {item.name}")
                print(f"    Period: {item.period_start_date} to {item.period_end_date}")
                print(f"    MRR: {item.mrr_per_month} NOK")
        else:
            print(f"\n[ERROR] Invoice {target_invoice} not found!")
            return

        print("\n" + "=" * 80)
        print("TEST 1: CURRENT APPROACH (First day of month - Sept 1)")
        print("=" * 80)

        # Current approach: first day of month
        stmt = select(InvoiceLineItem, Invoice).join(
            Invoice, InvoiceLineItem.invoice_id == Invoice.id
        ).where(
            and_(
                Invoice.customer_name == "ACE SJØMAT AS",
                InvoiceLineItem.period_start_date <= sept_first_day,
                InvoiceLineItem.period_end_date >= sept_first_day
            )
        )
        result = await session.execute(stmt)
        items_first_day = result.all()

        print(f"\nActive line items on Sept 1, 2025: {len(items_first_day)}")
        total_mrr_first_day = 0
        for item, inv in items_first_day:
            print(f"  Invoice: {inv.invoice_number}")
            print(f"    Item: {item.name}")
            print(f"    Period: {item.period_start_date} to {item.period_end_date}")
            print(f"    MRR: {item.mrr_per_month} NOK")
            total_mrr_first_day += item.mrr_per_month or 0

        print(f"\nTotal MRR (first day approach): {total_mrr_first_day} NOK")

        # Check specifically for invoice 2010783
        found_2010783 = any(inv.invoice_number == target_invoice for item, inv in items_first_day)
        print(f"Invoice 2010783 included: {'YES' if found_2010783 else 'NO'}")

        print("\n" + "=" * 80)
        print("TEST 2: MONTH-END SNAPSHOT APPROACH (Last day of month - Sept 30)")
        print("=" * 80)

        # Month-end approach: last day of month
        stmt = select(InvoiceLineItem, Invoice).join(
            Invoice, InvoiceLineItem.invoice_id == Invoice.id
        ).where(
            and_(
                Invoice.customer_name == "ACE SJØMAT AS",
                InvoiceLineItem.period_start_date <= sept_last_day,
                InvoiceLineItem.period_end_date >= sept_last_day
            )
        )
        result = await session.execute(stmt)
        items_last_day = result.all()

        print(f"\nActive line items on Sept 30, 2025: {len(items_last_day)}")
        total_mrr_last_day = 0
        for item, inv in items_last_day:
            print(f"  Invoice: {inv.invoice_number}")
            print(f"    Item: {item.name}")
            print(f"    Period: {item.period_start_date} to {item.period_end_date}")
            print(f"    MRR: {item.mrr_per_month} NOK")
            total_mrr_last_day += item.mrr_per_month or 0

        print(f"\nTotal MRR (month-end approach): {total_mrr_last_day} NOK")

        # Check specifically for invoice 2010783
        found_2010783_last = any(inv.invoice_number == target_invoice for item, inv in items_last_day)
        print(f"Invoice 2010783 included: {'YES' if found_2010783_last else 'NO'}")

        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)
        print(f"Difference in line items: {len(items_last_day) - len(items_first_day)}")
        print(f"Difference in MRR: {total_mrr_last_day - total_mrr_first_day} NOK")

        if found_2010783 != found_2010783_last:
            print("\n⚠️  CRITICAL: Invoice 2010783 appears in one approach but not the other!")
            print(f"   First day (Sept 1): {'FOUND' if found_2010783 else 'MISSING'}")
            print(f"   Last day (Sept 30): {'FOUND' if found_2010783_last else 'MISSING'}")

        # Detailed check on invoice 2010783 line item
        print("\n" + "=" * 80)
        print("DETAILED CHECK: Why is 2010783 missing?")
        print("=" * 80)

        stmt = select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
        result = await session.execute(stmt)
        line_items = result.scalars().all()

        for item in line_items:
            print(f"\nLine item: {item.name}")
            print(f"Period start: {item.period_start_date}")
            print(f"Period end: {item.period_end_date}")
            print(f"Sept 1, 2025: {sept_first_day}")
            print(f"Sept 30, 2025: {sept_last_day}")

            # Check conditions
            start_before_sept1 = item.period_start_date <= sept_first_day
            end_after_sept1 = item.period_end_date >= sept_first_day
            active_sept1 = start_before_sept1 and end_after_sept1

            start_before_sept30 = item.period_start_date <= sept_last_day
            end_after_sept30 = item.period_end_date >= sept_last_day
            active_sept30 = start_before_sept30 and end_after_sept30

            print(f"\nSept 1 check:")
            print(f"  period_start_date <= sept_first_day: {start_before_sept1}")
            print(f"  period_end_date >= sept_first_day: {end_after_sept1}")
            print(f"  Active on Sept 1: {active_sept1}")

            print(f"\nSept 30 check:")
            print(f"  period_start_date <= sept_last_day: {start_before_sept30}")
            print(f"  period_end_date >= sept_last_day: {end_after_sept30}")
            print(f"  Active on Sept 30: {active_sept30}")

            if active_sept1 != active_sept30:
                print("\n⚠️  INCONSISTENCY FOUND!")

if __name__ == "__main__":
    asyncio.run(test_date_filtering())
