"""
INVESTIGATE BIG MISMATCHES
Detailed investigation of customers with large MRR mismatches
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from models.subscription import Subscription
from sqlalchemy import select


async def investigate_customer(session, customer_name: str, target_month_end):
    """Investigate a specific customer's subscription and invoice data"""

    print("\n" + "=" * 120)
    print(f"CUSTOMER: {customer_name}")
    print("=" * 120)

    # Get all subscriptions for this customer
    sub_result = await session.execute(
        select(Subscription).where(
            Subscription.customer_name == customer_name,
            Subscription.status.in_(['live', 'non_renewing'])
        )
    )
    subscriptions = sub_result.scalars().all()

    print(f"\n[SUBSCRIPTIONS] Found {len(subscriptions)} active subscriptions:")
    total_sub_mrr = 0

    for i, sub in enumerate(subscriptions, 1):
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
            interval_display = "year"
        elif interval_unit == 'months':
            mrr = (amount / 1.25) / interval
            interval_display = f"{interval} month(s)"
        else:
            mrr = amount / 1.25
            interval_display = "unknown"

        total_sub_mrr += mrr

        created_str = sub.created_time.strftime('%Y-%m-%d') if sub.created_time else 'Unknown'

        print(f"\n  {i}. Subscription ID: {sub.id}")
        print(f"     Plan: {sub.plan_name}")
        print(f"     Status: {sub.status}")
        print(f"     Amount (incl VAT): {amount:,.2f} NOK")
        print(f"     Interval: {interval_display}")
        print(f"     MRR (excl VAT): {mrr:,.2f} NOK")
        print(f"     Created: {created_str}")
        print(f"     Vessel: {sub.vessel_name or 'N/A'}")
        print(f"     Call Sign: {sub.call_sign or 'N/A'}")

    print(f"\n  TOTAL SUBSCRIPTION MRR: {total_sub_mrr:,.2f} NOK")

    # Get all invoice line items for this customer active in September
    inv_result = await session.execute(
        select(InvoiceLineItem, Invoice).join(
            Invoice, InvoiceLineItem.invoice_id == Invoice.id
        ).where(
            Invoice.customer_name == customer_name,
            InvoiceLineItem.period_start_date <= target_month_end,
            InvoiceLineItem.period_end_date >= target_month_end
        ).order_by(Invoice.invoice_number, InvoiceLineItem.id)
    )
    invoice_rows = inv_result.all()

    print(f"\n[INVOICES] Found {len(invoice_rows)} invoice line items active in September 2025:")
    total_inv_mrr = 0
    total_positive = 0
    total_negative = 0

    current_invoice = None

    for i, (line_item, invoice) in enumerate(invoice_rows, 1):
        mrr = line_item.mrr_per_month or 0
        total_inv_mrr += mrr

        if mrr > 0:
            total_positive += mrr
        else:
            total_negative += mrr

        # Print invoice header if new invoice
        if current_invoice != invoice.invoice_number:
            current_invoice = invoice.invoice_number
            inv_date_str = invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else 'N/A'
            print(f"\n  Invoice: {invoice.invoice_number} ({invoice.transaction_type}) - Date: {inv_date_str}")

        period_start_str = line_item.period_start_date.strftime('%Y-%m-%d') if line_item.period_start_date else 'N/A'
        period_end_str = line_item.period_end_date.strftime('%Y-%m-%d') if line_item.period_end_date else 'N/A'

        print(f"    - {line_item.name}")
        print(f"      Period: {period_start_str} to {period_end_str} ({line_item.period_months or 0} months)")
        print(f"      Item Total: {line_item.item_total or 0:,.2f} NOK")
        print(f"      MRR: {mrr:,.2f} NOK")
        if line_item.subscription_id:
            print(f"      Linked to Subscription: {line_item.subscription_id}")

    print(f"\n  INVOICE MRR BREAKDOWN:")
    print(f"    Positive (Invoices): {total_positive:,.2f} NOK")
    print(f"    Negative (Credit Notes): {total_negative:,.2f} NOK")
    print(f"    TOTAL INVOICE MRR: {total_inv_mrr:,.2f} NOK")

    # Calculate difference
    diff = total_inv_mrr - total_sub_mrr
    diff_pct = (diff / total_sub_mrr * 100) if total_sub_mrr > 0 else 0

    print(f"\n[ANALYSIS]")
    print(f"  Subscription MRR: {total_sub_mrr:,.2f} NOK")
    print(f"  Invoice MRR:      {total_inv_mrr:,.2f} NOK")
    print(f"  Difference:       {diff:,.2f} NOK ({diff_pct:.1f}%)")

    if abs(diff) > 100:
        print(f"\n[POTENTIAL CAUSES]")

        if total_negative < -100:
            print(f"  1. Credit notes reduce invoice MRR by {abs(total_negative):,.2f} NOK")

        # Check if subscriptions are linked to invoices
        sub_ids = {sub.id for sub in subscriptions}
        inv_sub_ids = {line_item.subscription_id for line_item, _ in invoice_rows if line_item.subscription_id}

        unlinked_subs = sub_ids - inv_sub_ids
        if unlinked_subs:
            print(f"  2. {len(unlinked_subs)} subscription(s) not linked to any invoice in September")
            print(f"     Subscription IDs: {', '.join(unlinked_subs)}")

        # Check for invoices without subscription links
        inv_without_sub = sum(1 for line_item, _ in invoice_rows if not line_item.subscription_id)
        if inv_without_sub > 0:
            print(f"  3. {inv_without_sub} invoice line(s) not linked to any subscription")

        # Check period mismatches
        if len(subscriptions) != len(set(inv_sub_ids)):
            print(f"  4. Number of subscriptions ({len(subscriptions)}) != number of unique subscription IDs in invoices ({len(inv_sub_ids)})")

    print("=" * 120)


async def main():
    """Investigate top customers with biggest mismatches"""

    target_month_end = datetime(2025, 9, 30, 23, 59, 59)

    # List of customers to investigate (from previous analysis)
    customers_to_investigate = [
        "Nergård Havfiske AS",
        "SELVÅG SENIOR AS",
        "ENGENESFISK DRIFT AS",
        "TOR ARNT AS",
        "FORRÅY AS",
    ]

    print("=" * 120)
    print("INVESTIGATING CUSTOMERS WITH BIG MRR MISMATCHES - SEPTEMBER 2025")
    print("=" * 120)

    async with AsyncSessionLocal() as session:
        for customer_name in customers_to_investigate:
            await investigate_customer(session, customer_name, target_month_end)


if __name__ == "__main__":
    asyncio.run(main())
