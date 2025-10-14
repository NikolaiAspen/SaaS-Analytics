"""
Check the specific customers mentioned by the user
to understand why gap analysis says they have "no subscriptions"
"""

import asyncio
from database import AsyncSessionLocal
from models.subscription import Subscription
from models.invoice import Invoice, InvoiceLineItem
from sqlalchemy import select
from datetime import datetime


async def check_customers():
    """Check specific customers that should have subscriptions"""

    target_subscriptions = {
        '175017000011170055': 'Talbor',
        '175017000013265886': 'Vågøy',
        '175017000014105480': 'S Johansen',
        '175017000005487228': 'Cathmar',
        '175017000012114029': 'Småvær'
    }

    async with AsyncSessionLocal() as session:
        print("="*100)
        print("CHECKING SPECIFIC CUSTOMERS WITH SUBSCRIPTION IDS")
        print("="*100)

        for sub_id, vessel in target_subscriptions.items():
            print(f"\n{vessel.upper()} - Subscription ID: {sub_id}")
            print("-"*100)

            # Check if subscription exists
            stmt = select(Subscription).where(Subscription.id == sub_id)
            result = await session.execute(stmt)
            sub = result.scalar_one_or_none()

            if sub:
                print(f"  [OK] SUBSCRIPTION FOUND")
                print(f"     Customer: {sub.customer_name}")
                print(f"     Status: {sub.status}")
                print(f"     Plan: {sub.plan_name}")
                print(f"     Vessel: {sub.vessel_name}")
                print(f"     Call Sign: {sub.call_sign}")
                print(f"     Amount: {sub.amount}")
                print(f"     Interval: {sub.interval} {sub.interval_unit}")
            else:
                print(f"  [ERROR] SUBSCRIPTION NOT FOUND")

            # Check for invoices in September 2025
            print(f"\n  Invoices in September 2025:")
            target_start = datetime(2025, 9, 1)
            target_end = datetime(2025, 9, 30)

            stmt = select(InvoiceLineItem, Invoice).join(
                Invoice, InvoiceLineItem.invoice_id == Invoice.id
            ).where(
                InvoiceLineItem.subscription_id == sub_id,
                InvoiceLineItem.period_start_date <= target_end,
                InvoiceLineItem.period_end_date >= target_start
            )
            result = await session.execute(stmt)
            invoice_rows = result.all()

            if invoice_rows:
                print(f"     Found {len(invoice_rows)} invoice line items:")
                for line_item, invoice in invoice_rows:
                    print(f"       - Invoice: {invoice.invoice_number}")
                    print(f"         Customer: {invoice.customer_name}")
                    print(f"         Item: {line_item.name}")
                    print(f"         MRR: {line_item.mrr_per_month:.2f} kr")
                    print(f"         Vessel: {getattr(line_item, 'vessel_name', 'N/A')}")
                    print(f"         Call Sign: {getattr(line_item, 'call_sign', 'N/A')}")
            else:
                print(f"     No invoices found with subscription_id = {sub_id}")

                # Check if there are invoices for this vessel/customer without subscription_id
                if sub:
                    print(f"\n  Checking for invoices by customer name: {sub.customer_name}")
                    stmt = select(InvoiceLineItem, Invoice).join(
                        Invoice, InvoiceLineItem.invoice_id == Invoice.id
                    ).where(
                        Invoice.customer_name == sub.customer_name,
                        InvoiceLineItem.period_start_date <= target_end,
                        InvoiceLineItem.period_end_date >= target_start
                    )
                    result = await session.execute(stmt)
                    invoice_rows = result.all()

                    if invoice_rows:
                        print(f"     Found {len(invoice_rows)} invoice line items by customer name:")
                        for line_item, invoice in invoice_rows:
                            print(f"       - Invoice: {invoice.invoice_number}")
                            print(f"         Item: {line_item.name}")
                            print(f"         MRR: {line_item.mrr_per_month:.2f} kr")
                            print(f"         Subscription ID in invoice: {line_item.subscription_id or 'MISSING'}")
                            print(f"         Vessel: {getattr(line_item, 'vessel_name', 'N/A')}")
                            print(f"         Call Sign: {getattr(line_item, 'call_sign', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(check_customers())
