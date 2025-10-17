"""
Check why specific vessels show as missing invoices in gap analysis
"""
import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal
from models.subscription import Subscription
from models.invoice import Invoice, InvoiceLineItem

async def check_vessels():
    """Check invoice data for specific call signs"""

    call_signs = ['LK2169', 'LF6691', 'LK7481']

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print("CHECKING MISSING INVOICES FOR VESSELS")
        print("=" * 80)

        for call_sign in call_signs:
            print(f"\n{'='*80}")
            print(f"Call Sign: {call_sign}")
            print(f"{'='*80}")

            # Check subscription
            stmt = select(Subscription).where(Subscription.call_sign == call_sign)
            result = await session.execute(stmt)
            subs = result.scalars().all()

            if subs:
                print(f"\n[OK] SUBSCRIPTION(S) FOUND: {len(subs)}")
                for sub in subs:
                    print(f"\n  Subscription {sub.id}:")
                    print(f"    Customer: {sub.customer_name}")
                    print(f"    Vessel: {sub.vessel_name}")
                    print(f"    Plan: {sub.plan_name}")
                    print(f"    Status: {sub.status}")
                    print(f"    Amount: {sub.amount} NOK")
            else:
                print(f"\n[MISSING] NO SUBSCRIPTION FOUND")
                continue

            # Use first subscription for customer name lookup
            sub = subs[0]

            # Check invoice line items with this call sign
            stmt = select(InvoiceLineItem).where(
                InvoiceLineItem.call_sign == call_sign
            )
            result = await session.execute(stmt)
            line_items = result.scalars().all()

            if line_items:
                print(f"\n[OK] INVOICE LINE ITEMS FOUND: {len(line_items)}")
                for item in line_items:
                    invoice = await session.get(Invoice, item.invoice_id)
                    print(f"\n  Invoice: {item.invoice_id}")
                    print(f"    Customer: {invoice.customer_name if invoice else 'N/A'}")
                    print(f"    Item: {item.name}")
                    print(f"    Period: {item.period_start_date} to {item.period_end_date}")
                    print(f"    MRR: {item.mrr_per_month} NOK")
            else:
                print(f"\n[MISSING] NO INVOICE LINE ITEMS FOUND WITH CALL_SIGN = '{call_sign}'")

                # Check if there are invoices for the customer name
                stmt = select(Invoice).where(
                    Invoice.customer_name == sub.customer_name
                )
                result = await session.execute(stmt)
                invoices = result.scalars().all()

                if invoices:
                    print(f"\n  Found {len(invoices)} invoices for customer '{sub.customer_name}':")
                    for inv in invoices[:5]:  # Show first 5
                        print(f"    Invoice {inv.invoice_number} - {inv.invoice_date}")

                        # Check line items for this invoice
                        stmt = select(InvoiceLineItem).where(
                            InvoiceLineItem.invoice_id == inv.id
                        )
                        result = await session.execute(stmt)
                        items = result.scalars().all()

                        for item in items:
                            print(f"      - {item.name} | call_sign: '{item.call_sign}' | vessel: '{item.vessel_name}'")
                else:
                    print(f"\n  No invoices found for customer '{sub.customer_name}'")

        print("\n" + "=" * 80)
        print("INVESTIGATION COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(check_vessels())
