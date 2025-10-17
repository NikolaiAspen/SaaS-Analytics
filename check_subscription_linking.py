"""
Check subscription linking between invoices and subscriptions
Investigate if subscription_id exists and can be used for linking
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from models.subscription import Subscription
from sqlalchemy import select, func


async def check_linking():
    """Check if invoices are linked to subscriptions via subscription_id"""

    print("=" * 120)
    print("CHECKING SUBSCRIPTION LINKING IN DATABASE")
    print("=" * 120)

    async with AsyncSessionLocal() as session:
        # Check how many invoice line items have subscription_id
        print("\n[1/5] Checking subscription_id in invoice_line_items...")

        total_count = await session.execute(select(func.count(InvoiceLineItem.id)))
        total = total_count.scalar()

        with_sub_id_count = await session.execute(
            select(func.count(InvoiceLineItem.id)).where(InvoiceLineItem.subscription_id.isnot(None))
        )
        with_sub_id = with_sub_id_count.scalar()

        without_sub_id = total - with_sub_id

        print(f"  Total invoice line items: {total}")
        print(f"  With subscription_id: {with_sub_id} ({with_sub_id/total*100:.1f}%)")
        print(f"  Without subscription_id: {without_sub_id} ({without_sub_id/total*100:.1f}%)")

        # Show examples of invoices WITH subscription_id
        if with_sub_id > 0:
            print(f"\n[2/5] Examples of invoice lines WITH subscription_id:")
            result = await session.execute(
                select(InvoiceLineItem, Invoice).join(
                    Invoice, InvoiceLineItem.invoice_id == Invoice.id
                ).where(
                    InvoiceLineItem.subscription_id.isnot(None)
                ).limit(10)
            )
            rows = result.all()

            for i, (line_item, invoice) in enumerate(rows[:5], 1):
                print(f"\n  {i}. Invoice: {invoice.invoice_number} - Customer: {invoice.customer_name}")
                print(f"     Item: {line_item.name}")
                print(f"     Subscription ID: {line_item.subscription_id}")
                print(f"     MRR: {line_item.mrr_per_month:,.2f} NOK")
        else:
            print(f"\n[2/5] NO invoice lines have subscription_id!")

        # Check if we can match via call sign
        print(f"\n[3/5] Checking if we can match via vessel/call sign...")

        # Get a sample subscription
        sub_result = await session.execute(
            select(Subscription).where(
                Subscription.status.in_(['live', 'non_renewing']),
                Subscription.call_sign.isnot(None)
            ).limit(1)
        )
        sample_sub = sub_result.scalar_one_or_none()

        if sample_sub:
            print(f"\n  Sample Subscription:")
            print(f"    ID: {sample_sub.id}")
            print(f"    Customer: {sample_sub.customer_name}")
            print(f"    Plan: {sample_sub.plan_name}")
            print(f"    Vessel: {sample_sub.vessel_name}")
            print(f"    Call Sign: {sample_sub.call_sign}")

            # Try to find matching invoices
            target_month_end = datetime(2025, 9, 30, 23, 59, 59)

            inv_result = await session.execute(
                select(InvoiceLineItem, Invoice).join(
                    Invoice, InvoiceLineItem.invoice_id == Invoice.id
                ).where(
                    Invoice.customer_name == sample_sub.customer_name,
                    InvoiceLineItem.period_start_date <= target_month_end,
                    InvoiceLineItem.period_end_date >= target_month_end
                ).limit(5)
            )
            inv_rows = inv_result.all()

            print(f"\n  Matching Invoices (same customer, active in Sept 2025):")
            if inv_rows:
                for i, (line_item, invoice) in enumerate(inv_rows, 1):
                    print(f"\n    {i}. Invoice: {invoice.invoice_number}")
                    print(f"       Item: {line_item.name}")
                    print(f"       Vessel: {getattr(line_item, 'vessel_name', 'N/A')}")
                    print(f"       Call Sign: {getattr(line_item, 'call_sign', 'N/A')}")
                    print(f"       Subscription ID in invoice: {line_item.subscription_id or 'NONE'}")
                    print(f"       MRR: {line_item.mrr_per_month:,.2f} NOK")
            else:
                print("    No matching invoices found")

        # Check Zoho API structure
        print(f"\n[4/5] Checking what data we import from Zoho API...")

        # Get sample invoice from database
        inv_sample_result = await session.execute(
            select(InvoiceLineItem).limit(1)
        )
        sample_inv = inv_sample_result.scalar_one_or_none()

        if sample_inv:
            print(f"\n  Sample Invoice Line Item fields:")
            print(f"    - id: {sample_inv.id}")
            print(f"    - invoice_id: {sample_inv.invoice_id}")
            print(f"    - subscription_id: {sample_inv.subscription_id or 'NULL'}")
            print(f"    - name: {sample_inv.name}")
            print(f"    - mrr_per_month: {sample_inv.mrr_per_month}")

        # Recommendations
        print(f"\n[5/5] ANALYSIS & RECOMMENDATIONS:")
        print("=" * 120)

        if with_sub_id == 0:
            print("\n  ❌ PROBLEM: NO invoices are linked to subscriptions via subscription_id")
            print("\n  POSSIBLE CAUSES:")
            print("    1. Zoho Billing doesn't include subscription_id in invoice API response")
            print("    2. subscription_id field exists but is not populated in Zoho")
            print("    3. We're not extracting subscription_id from Zoho API response")
            print("\n  SOLUTIONS:")
            print("    A. Check Zoho Billing API documentation for subscription_id field")
            print("    B. Verify if subscription_id exists in Zoho web interface")
            print("    C. Update import script to extract subscription_id if available")
            print("    D. Alternative: Use vessel/call_sign matching (current method)")
            print("\n  RECOMMENDATION:")
            print("    → Check import_invoices_xlsx.py to see if subscription_id is in Excel file")
            print("    → If yes: Update import script to extract it")
            print("    → If no: This is a Zoho configuration issue - contact Zoho support")
        else:
            print(f"\n  ✅ GOOD: {with_sub_id} invoices have subscription_id linked")
            print(f"  ⚠️  BUT: {without_sub_id} invoices are NOT linked")
            print("\n  ACTION: Investigate why only some invoices have subscription_id")

        print("\n" + "=" * 120)


if __name__ == "__main__":
    asyncio.run(check_linking())
