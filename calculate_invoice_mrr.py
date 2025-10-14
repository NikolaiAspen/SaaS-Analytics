"""
Calculate invoice-based MRR for October 2025
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def calculate_invoice_mrr():
    """Calculate invoice-based MRR for October 2025"""

    print("="*80)
    print("INVOICE-BASED MRR - OCTOBER 2025")
    print("="*80)

    target_month_start = datetime(2025, 10, 1)
    target_month_end = datetime(2025, 10, 31)

    async with AsyncSessionLocal() as session:
        # Get all line items with periods that overlap October 2025
        result = await session.execute(
            select(InvoiceLineItem)
            .join(Invoice)
            .where(
                InvoiceLineItem.period_start_date.isnot(None),
                InvoiceLineItem.period_end_date.isnot(None),
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_start
            )
            .options(selectinload(InvoiceLineItem.invoice))
        )
        line_items = result.scalars().all()

        total_mrr = 0
        customer_ids = set()
        invoice_count = 0
        creditnote_count = 0

        for item in line_items:
            mrr = float(item.mrr_per_month or 0)
            total_mrr += mrr
            customer_ids.add(item.invoice.customer_id)

            if item.invoice.transaction_type == 'invoice':
                invoice_count += 1
            elif item.invoice.transaction_type == 'creditnote':
                creditnote_count += 1

        print(f"\nTotal Invoice-based MRR: {total_mrr:,.2f} NOK")
        print(f"Total Customers: {len(customer_ids)}")
        print(f"Invoice line items: {invoice_count}")
        print(f"Credit note line items: {creditnote_count}")
        print(f"Total line items: {len(line_items)}")

        # Get subscription-based MRR for comparison
        from models.subscription import Subscription

        result = await session.execute(
            select(Subscription)
            .where(Subscription.status.in_(['live', 'non_renewing']))
        )
        subscriptions = result.scalars().all()

        subscription_mrr = 0
        for sub in subscriptions:
            amount = float(sub.amount or 0)
            vat_exclusive = amount / 1.25

            # Handle interval and interval_unit
            interval_val = sub.interval
            interval_unit = str(sub.interval_unit or 'months').lower()

            # Check if interval contains unit name (data inconsistency)
            if isinstance(interval_val, str):
                if interval_val.lower() in ['years', 'months']:
                    # Swap: interval contains unit, interval_unit contains number
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
                mrr = vat_exclusive / 12
            elif interval_unit == 'months':
                mrr = vat_exclusive / interval
            else:
                mrr = vat_exclusive

            subscription_mrr += mrr

        print("\n" + "="*80)
        print("COMPARISON")
        print("="*80)
        print(f"Subscription-based MRR: {subscription_mrr:,.2f} NOK")
        print(f"Invoice-based MRR:     {total_mrr:,.2f} NOK")

        diff = subscription_mrr - total_mrr
        diff_pct = (diff / subscription_mrr * 100) if subscription_mrr > 0 else 0

        print(f"\nDifference: {diff:,.2f} NOK ({diff_pct:.1f}%)")


if __name__ == "__main__":
    asyncio.run(calculate_invoice_mrr())
