"""
Regenerate all accounting MRR snapshots for months with data

This calculates snapshots using the corrected periodization logic
"""

import asyncio
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, func
from database import AsyncSessionLocal
from models.accounting import AccountingReceivableItem, AccountingMRRSnapshot
from services.accounting import AccountingService

async def regenerate_all_snapshots():
    print("\n" + "="*80)
    print("REGENERATING ALL ACCOUNTING MRR SNAPSHOTS")
    print("="*80 + "\n")

    async with AsyncSessionLocal() as session:
        service = AccountingService(session)

        # Get all unique source_months from the data
        result = await session.execute(
            select(AccountingReceivableItem.source_month)
            .distinct()
            .order_by(AccountingReceivableItem.source_month)
        )
        source_months = [row[0] for row in result.fetchall()]

        print(f"Found {len(source_months)} months with data:")
        for month in source_months:
            print(f"  - {month}")
        print()

        # Generate snapshots for each month
        for i, source_month in enumerate(source_months, 1):
            print(f"[{i}/{len(source_months)}] Generating snapshot for {source_month}...")

            try:
                # Generate and save snapshot using generate_monthly_snapshot
                snapshot = await service.generate_monthly_snapshot(source_month)
                print(f"  [OK] Snapshot saved for {source_month}")
                print(f"      MRR: {snapshot.mrr:,.2f} kr")
                print(f"      Customers: {snapshot.total_customers}")
                print(f"      Items: {snapshot.total_invoice_items} invoices, {snapshot.total_creditnote_items} credit notes\n")
            except Exception as e:
                print(f"  [ERROR] Failed to generate snapshot: {e}\n")
                import traceback
                traceback.print_exc()
                continue

    print("="*80)
    print("[SUCCESS] All snapshots regenerated")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(regenerate_all_snapshots())
