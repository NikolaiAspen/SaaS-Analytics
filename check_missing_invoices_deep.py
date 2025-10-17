"""
Check if customers with "subscriptions but no invoices" actually have invoices in the database
but just not active in October 2025
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from models.subscription import Subscription
from sqlalchemy import select


async def check_missing_invoices():
    """Check if invoices exist but are just not active in October"""

    target_month_end = datetime(2025, 10, 31, 23, 59, 59)

    print("=" * 120)
    print("CHECKING: Do 'subscriptions without invoices' actually have invoices?")
    print("=" * 120)

    async with AsyncSessionLocal() as session:
        # Get subscriptions active in October
        print("\n[1/3] Loading subscriptions active in October 2025...")
        sub_result = await session.execute(
            select(Subscription).where(Subscription.status.in_(['live', 'non_renewing']))
        )
        subscriptions = sub_result.scalars().all()

        # Calculate subscription MRR by customer
        sub_mrr_by_customer = {}

        for sub in subscriptions:
            amount = float(sub.amount or 0)
            interval_unit = str(sub.interval_unit or 'months').lower()
            interval_val = sub.interval

            if isinstance(interval_val, str):
                if interval_val.lower() in ['years', 'months']:
                    interval_unit = interval_val.lower()
                    interval = 1
                else:
                    try:
                        interval = int(interval_val)
                    except:
                        interval = 1
            else:
                interval = int(interval_val or 1)

            if interval_unit == 'years':
                mrr = (amount / 1.25) / 12
            elif interval_unit == 'months':
                mrr = (amount / 1.25) / interval
            else:
                mrr = amount / 1.25

            customer_name = sub.customer_name

            if customer_name not in sub_mrr_by_customer:
                sub_mrr_by_customer[customer_name] = 0

            sub_mrr_by_customer[customer_name] += mrr

        print(f"  [OK] {len(subscriptions)} subscriptions from {len(sub_mrr_by_customer)} customers")

        # Get invoices active in October 2025
        print("\n[2/3] Loading invoices ACTIVE in October 2025...")
        inv_result = await session.execute(
            select(InvoiceLineItem, Invoice)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_end
            )
        )
        invoice_rows_october = inv_result.all()

        inv_customers_october = set()
        for line_item, invoice in invoice_rows_october:
            inv_customers_october.add(invoice.customer_name)

        print(f"  [OK] {len(invoice_rows_october)} invoice lines from {len(inv_customers_october)} customers")

        # Get ALL invoices (any period)
        print("\n[3/3] Loading ALL invoices (any period) from database...")
        all_inv_result = await session.execute(
            select(Invoice.customer_name, Invoice.invoice_number, Invoice.invoice_date, InvoiceLineItem.period_start_date, InvoiceLineItem.period_end_date, InvoiceLineItem.name)
            .join(InvoiceLineItem, InvoiceLineItem.invoice_id == Invoice.id)
        )
        all_invoices = all_inv_result.all()

        # Group by customer
        invoices_by_customer = {}
        for customer_name, inv_number, inv_date, period_start, period_end, item_name in all_invoices:
            if customer_name not in invoices_by_customer:
                invoices_by_customer[customer_name] = []
            invoices_by_customer[customer_name].append({
                'invoice_number': inv_number,
                'invoice_date': inv_date,
                'period_start': period_start,
                'period_end': period_end,
                'item_name': item_name,
            })

        print(f"  [OK] Total {len(all_invoices)} invoice lines from {len(invoices_by_customer)} customers (all periods)")

        # Find customers with subscriptions but NO invoices in October
        print("\n" + "=" * 120)
        print("ANALYSIS: Customers with subscriptions but no invoices ACTIVE in October 2025")
        print("=" * 120)

        customers_sub_no_oct_inv = []
        for customer_name, sub_mrr in sub_mrr_by_customer.items():
            if customer_name not in inv_customers_october:
                customers_sub_no_oct_inv.append(customer_name)

        print(f"\nFound {len(customers_sub_no_oct_inv)} customers with subscriptions but no invoices active in October")

        # Check if they have invoices in OTHER periods
        has_invoices_other_periods = 0
        has_no_invoices_at_all = 0

        print("\nChecking if these customers have invoices in OTHER periods...")
        print("\n" + "-" * 120)

        for i, customer_name in enumerate(customers_sub_no_oct_inv[:20], 1):  # Show first 20
            sub_mrr = sub_mrr_by_customer[customer_name]

            if customer_name in invoices_by_customer:
                has_invoices_other_periods += 1
                invoices = invoices_by_customer[customer_name]

                print(f"\n{i}. {customer_name} (Subscription MRR: {sub_mrr:,.2f} NOK)")
                print(f"   ✓ HAS INVOICES in database ({len(invoices)} invoice lines)")
                print(f"   But NOT active in October 2025. Invoice periods:")

                for inv in invoices[:5]:  # Show first 5 invoices
                    period_str = ""
                    if inv['period_start'] and inv['period_end']:
                        period_str = f"{inv['period_start'].strftime('%Y-%m-%d')} to {inv['period_end'].strftime('%Y-%m-%d')}"
                    else:
                        period_str = "No period dates"

                    print(f"     - Invoice {inv['invoice_number']}: {inv['item_name']}")
                    print(f"       Period: {period_str}")
                    print(f"       Invoice Date: {inv['invoice_date'].strftime('%Y-%m-%d') if inv['invoice_date'] else 'N/A'}")
            else:
                has_no_invoices_at_all += 1
                print(f"\n{i}. {customer_name} (Subscription MRR: {sub_mrr:,.2f} NOK)")
                print(f"   ✗ NO INVOICES in database at all!")

        print("\n" + "=" * 120)
        print("SUMMARY")
        print("=" * 120)
        print(f"\nCustomers with subscriptions but no invoices active in October: {len(customers_sub_no_oct_inv)}")
        print(f"  - Have invoices in OTHER periods: {has_invoices_other_periods}")
        print(f"  - Have NO invoices at all:        {has_no_invoices_at_all}")
        print("\n" + "=" * 120)

        if has_no_invoices_at_all > 0:
            print(f"\n⚠️  WARNING: {has_no_invoices_at_all} customers have subscriptions but NO invoices in database!")
            print("This suggests invoices are missing from the database.")


if __name__ == "__main__":
    asyncio.run(check_missing_invoices())
