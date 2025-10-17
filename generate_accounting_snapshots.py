"""
Generate accounting MRR snapshots for all imported months

Usage:
    python generate_accounting_snapshots.py
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from services.accounting import AccountingService
from sqlalchemy import select
from models.accounting import AccountingReceivableItem


async def generate_all_snapshots():
    """Generate snapshots for all months with imported data"""

    print(f"\n{'='*120}")
    print(f"GENERATING ACCOUNTING MRR SNAPSHOTS")
    print(f"{'='*120}")

    async with AsyncSessionLocal() as session:
        # Get all unique source_month values
        stmt = select(AccountingReceivableItem.source_month).distinct().order_by(AccountingReceivableItem.source_month)
        result = await session.execute(stmt)
        months = [row[0] for row in result.all()]

        print(f"\nFound {len(months)} months with data: {', '.join(months)}")
        print(f"\nGenerating snapshots...\n")

        service = AccountingService(session)

        for i, month in enumerate(months, 1):
            try:
                print(f"[{i}/{len(months)}] Generating snapshot for {month}...")
                snapshot = await service.generate_monthly_snapshot(month)

                # Parse month for display
                month_date = datetime.strptime(month, "%Y-%m")
                month_name = month_date.strftime("%B %Y")

                print(f"  [OK] {month_name}")
                print(f"    - MRR: {snapshot.mrr:,.2f} NOK")
                print(f"    - ARR: {snapshot.arr:,.2f} NOK")
                print(f"    - Customers: {snapshot.total_customers}")
                print(f"    - ARPU: {snapshot.arpu:,.2f} NOK")
                print(f"    - Invoice items: {snapshot.total_invoice_items} ({snapshot.invoice_mrr:,.2f} NOK)")
                print(f"    - Credit note items: {snapshot.total_creditnote_items} ({snapshot.creditnote_mrr:,.2f} NOK)")
                print()

            except Exception as e:
                print(f"  [ERROR] Failed: {e}")
                import traceback
                traceback.print_exc()
                continue

        print(f"{'='*120}")
        print(f"SNAPSHOT GENERATION COMPLETE")
        print(f"Generated {len(months)} snapshots")
        print(f"{'='*120}\n")


if __name__ == "__main__":
    asyncio.run(generate_all_snapshots())
