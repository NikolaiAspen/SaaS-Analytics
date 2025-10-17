"""
FIX INVOICE-SUBSCRIPTION LINKING
Automatically link old invoices to subscriptions using call sign and vessel name matching
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import InvoiceLineItem, Invoice
from models.subscription import Subscription
from sqlalchemy import select


async def fix_linking():
    """Fix subscription linking for old invoices"""

    print("=" * 120)
    print("FIXING INVOICE-SUBSCRIPTION LINKING")
    print("=" * 120)

    async with AsyncSessionLocal() as session:
        # Get all subscriptions
        print("\n[1/4] Loading subscriptions...")
        sub_result = await session.execute(
            select(Subscription).where(Subscription.status.in_(['live', 'non_renewing']))
        )
        subscriptions = sub_result.scalars().all()

        # Build lookup dictionaries
        sub_by_call_sign = {}
        sub_by_vessel_customer = {}

        for sub in subscriptions:
            # Index by call sign
            if sub.call_sign:
                call_sign_clean = sub.call_sign.strip().upper()
                if call_sign_clean not in sub_by_call_sign:
                    sub_by_call_sign[call_sign_clean] = []
                sub_by_call_sign[call_sign_clean].append(sub)

            # Index by vessel + customer
            if sub.vessel_name and sub.customer_name:
                vessel_clean = sub.vessel_name.strip().upper()
                customer_clean = sub.customer_name.strip().upper()
                key = f"{vessel_clean}|{customer_clean}"
                if key not in sub_by_vessel_customer:
                    sub_by_vessel_customer[key] = []
                sub_by_vessel_customer[key].append(sub)

        print(f"  [OK] {len(subscriptions)} subscriptions loaded")
        print(f"  [OK] {len(sub_by_call_sign)} unique call signs")
        print(f"  [OK] {len(sub_by_vessel_customer)} unique vessel-customer combinations")

        # Get all invoice line items without subscription_id
        print("\n[2/4] Loading invoice line items without subscription_id...")
        inv_result = await session.execute(
            select(InvoiceLineItem, Invoice).join(
                Invoice, InvoiceLineItem.invoice_id == Invoice.id
            ).where(
                (InvoiceLineItem.subscription_id.is_(None)) | (InvoiceLineItem.subscription_id == '')
            )
        )
        invoice_rows = inv_result.all()

        print(f"  [OK] {len(invoice_rows)} invoice line items to link")

        # Match and update
        print("\n[3/4] Matching invoices to subscriptions...")

        matched_by_call_sign = 0
        matched_by_vessel = 0
        not_matched = 0
        updates = []

        for line_item, invoice in invoice_rows:
            matched_sub = None

            # Try call sign matching first
            if hasattr(line_item, 'call_sign') and line_item.call_sign:
                call_sign_clean = line_item.call_sign.strip().upper()
                if call_sign_clean in sub_by_call_sign:
                    # Found match by call sign - pick the first one (there might be multiple subscriptions for same vessel)
                    candidates = sub_by_call_sign[call_sign_clean]
                    # Filter by customer name
                    for sub in candidates:
                        if sub.customer_name == invoice.customer_name:
                            matched_sub = sub
                            matched_by_call_sign += 1
                            break

            # Try vessel + customer matching if call sign didn't work
            if not matched_sub and hasattr(line_item, 'vessel_name') and line_item.vessel_name:
                vessel_clean = line_item.vessel_name.strip().upper()
                customer_clean = invoice.customer_name.strip().upper()
                key = f"{vessel_clean}|{customer_clean}"
                if key in sub_by_vessel_customer:
                    matched_sub = sub_by_vessel_customer[key][0]
                    matched_by_vessel += 1

            if matched_sub:
                updates.append((line_item, matched_sub.id))
            else:
                not_matched += 1

        print(f"  [OK] Matched {len(updates)} invoice lines")
        print(f"    - By call sign: {matched_by_call_sign}")
        print(f"    - By vessel + customer: {matched_by_vessel}")
        print(f"    - Not matched: {not_matched}")

        # Apply updates (DRY RUN first)
        print(f"\n[4/4] Applying updates (DRY RUN - showing first 20)...")

        for i, (line_item, subscription_id) in enumerate(updates[:20], 1):
            print(f"  {i}. Invoice Line Item {line_item.id}:")
            print(f"     Will link to Subscription ID: {subscription_id}")

        # Ask for confirmation
        print(f"\n" + "=" * 120)
        print(f"SUMMARY:")
        print(f"  Total invoice lines to update: {len(updates)}")
        print(f"  Matched by call sign: {matched_by_call_sign}")
        print(f"  Matched by vessel: {matched_by_vessel}")
        print(f"  Not matched: {not_matched}")
        print("=" * 120)

        response = input(f"\nDo you want to apply these {len(updates)} updates? (yes/no): ")

        if response.lower() == 'yes':
            print(f"\nApplying updates...")
            for line_item, subscription_id in updates:
                line_item.subscription_id = subscription_id

            await session.commit()
            print(f"[SUCCESS] Updated {len(updates)} invoice line items with subscription_id!")
        else:
            print(f"\n[CANCELLED] No changes made.")


if __name__ == "__main__":
    asyncio.run(fix_linking())
