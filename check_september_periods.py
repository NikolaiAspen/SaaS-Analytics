"""
Check if invoices for these vessels are active in September 2025
"""
import asyncio
from datetime import datetime
from sqlalchemy import select, and_
from database import AsyncSessionLocal
from models.invoice import InvoiceLineItem

async def check_periods():
    """Check if invoice periods cover September 2025"""

    call_signs = ['LK2169', 'LF6691', 'LK7481']

    # September 2025 month-end
    sept_end = datetime(2025, 9, 30, 23, 59, 59)

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print("CHECKING SEPTEMBER 2025 COVERAGE")
        print(f"Target date: {sept_end}")
        print("=" * 80)

        for call_sign in call_signs:
            print(f"\n{'='*80}")
            print(f"Call Sign: {call_sign}")
            print(f"{'='*80}")

            # Get all invoice line items for this call sign
            stmt = select(InvoiceLineItem).where(
                InvoiceLineItem.call_sign == call_sign
            )
            result = await session.execute(stmt)
            all_items = result.scalars().all()

            print(f"\nTotal invoice line items: {len(all_items)}")

            # Check which are active on Sept 30, 2025
            stmt = select(InvoiceLineItem).where(
                and_(
                    InvoiceLineItem.call_sign == call_sign,
                    InvoiceLineItem.period_start_date <= sept_end,
                    InvoiceLineItem.period_end_date >= sept_end
                )
            )
            result = await session.execute(stmt)
            active_items = result.scalars().all()

            if active_items:
                print(f"\n[OK] Active in September: {len(active_items)} line items")
                for item in active_items:
                    print(f"\n  Invoice: {item.invoice_id}")
                    print(f"    Item: {item.name}")
                    print(f"    Period: {item.period_start_date} to {item.period_end_date}")
                    print(f"    MRR: {item.mrr_per_month} NOK")
            else:
                print(f"\n[MISSING] NOT active in September 2025")
                print(f"\nAll invoices for {call_sign}:")
                for item in all_items:
                    active_status = "ACTIVE" if (item.period_start_date <= sept_end and item.period_end_date >= sept_end) else "NOT ACTIVE"
                    print(f"\n  {active_status}: {item.name}")
                    print(f"    Period: {item.period_start_date} to {item.period_end_date}")
                    print(f"    Start after Sept? {item.period_start_date > sept_end}")
                    print(f"    End before Sept? {item.period_end_date < sept_end}")

        print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(check_periods())
