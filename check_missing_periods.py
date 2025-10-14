"""
Check items that are missing period dates
"""

import asyncio
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from sqlalchemy import select, and_


async def check_missing_periods():
    """Check how many items lack period dates"""

    async with AsyncSessionLocal() as session:
        # Count total line items
        result = await session.execute(
            select(InvoiceLineItem)
        )
        all_items = result.scalars().all()
        print(f"Total line items in database: {len(all_items)}")

        # Count items WITHOUT period dates
        result = await session.execute(
            select(InvoiceLineItem)
            .where(
                (InvoiceLineItem.period_start_date.is_(None)) |
                (InvoiceLineItem.period_end_date.is_(None))
            )
        )
        no_periods = result.scalars().all()
        print(f"Items WITHOUT period dates: {len(no_periods)}")

        # Count items WITH period dates
        result = await session.execute(
            select(InvoiceLineItem)
            .where(
                and_(
                    InvoiceLineItem.period_start_date.isnot(None),
                    InvoiceLineItem.period_end_date.isnot(None)
                )
            )
        )
        with_periods = result.scalars().all()
        print(f"Items WITH period dates: {len(with_periods)}")

        # Sample items without periods
        print("\n" + "="*80)
        print("SAMPLE ITEMS WITHOUT PERIOD DATES")
        print("="*80)

        from collections import Counter
        item_names = [item.name for item in no_periods]
        name_counts = Counter(item_names)

        print("\nTop 20 items without period dates:")
        for name, count in name_counts.most_common(20):
            print(f"{name}: {count}")

        # Show Satellittabonnement specifically
        print("\n" + "="*80)
        print("SATELLITTABONNEMENT ANALYSIS")
        print("="*80)

        satelitt_items = [item for item in all_items if 'Satelitt' in item.name]
        print(f"Total Satellittabonnement items: {len(satelitt_items)}")

        satelitt_no_period = [item for item in no_periods if 'Satelitt' in item.name]
        print(f"Satellittabonnement WITHOUT period dates: {len(satelitt_no_period)}")

        if len(satelitt_no_period) > 0:
            print("\nSample Satellittabonnement without periods:")
            for item in satelitt_no_period[:5]:
                print(f"  Name: {item.name}")
                print(f"  Description: {item.description}")
                print(f"  Price: {item.price}")
                print(f"  Quantity: {item.quantity}")
                print(f"  Period start: {item.period_start_date}")
                print(f"  Period end: {item.period_end_date}")
                print()


if __name__ == "__main__":
    asyncio.run(check_missing_periods())
