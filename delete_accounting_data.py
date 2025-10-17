"""
Delete all existing accounting data from database

This clears the slate for re-importing with corrected periodization
"""

import asyncio
from database import AsyncSessionLocal
from models.accounting import AccountingReceivableItem, AccountingMRRSnapshot
from sqlalchemy import delete

async def delete_all_accounting_data():
    print("\n" + "="*80)
    print("DELETING ALL ACCOUNTING DATA")
    print("="*80 + "\n")

    async with AsyncSessionLocal() as session:
        # Delete all snapshots
        print("[1/2] Deleting all MRR snapshots...")
        result = await session.execute(delete(AccountingMRRSnapshot))
        await session.commit()
        print(f"  [OK] Deleted {result.rowcount} snapshots\n")

        # Delete all receivable items
        print("[2/2] Deleting all receivable items...")
        result = await session.execute(delete(AccountingReceivableItem))
        await session.commit()
        print(f"  [OK] Deleted {result.rowcount} items\n")

    print("="*80)
    print("[SUCCESS] All accounting data deleted")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(delete_all_accounting_data())
