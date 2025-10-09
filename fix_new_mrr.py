"""
Fix New MRR values in monthly snapshots by calculating from Excel files
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from models.subscription import MonthlyMRRSnapshot
from services.zoho_import import ZohoReportImporter


async def main():
    engine = create_async_engine('sqlite+aiosqlite:///data/app.db')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Define the file pairs (current, previous) for calculating New MRR
    file_pairs = [
        # (current_file, previous_file, month)
        ('excel/Nov2024.xlsx', 'excel/Oct2024.xlsx', '2024-11'),
        ('excel/Dec2024.xlsx', 'excel/Nov2024.xlsx', '2024-12'),
        # Skip Jan 2025 - we don't have the file
        ('excel/MRR Details.xlsx', 'excel/Dec2024.xlsx', '2025-02'),  # Feb
        ('excel/MRR Details (1).xlsx', 'excel/MRR Details.xlsx', '2025-03'),  # Mar
    ]

    print('Calculating New MRR from Excel files...')
    print('')

    importer = ZohoReportImporter()
    updates = {}

    for current_file, previous_file, expected_month in file_pairs:
        try:
            result = importer.calculate_new_mrr(current_file, previous_file)
            month = result['month']
            new_mrr = result['new_mrr']
            updates[month] = new_mrr
            print(f'{month}: {new_mrr:>12,.0f} kr')
            print('')
        except Exception as e:
            print(f'Error processing {current_file}: {e}')
            print('')

    # Update database
    async with async_session() as session:
        print('Updating database...')
        print('')

        for month, new_mrr in updates.items():
            # Find the monthly snapshot
            stmt = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == month)
            result = await session.execute(stmt)
            snapshot = result.scalar_one_or_none()

            if snapshot:
                old_new_mrr = snapshot.new_mrr
                snapshot.new_mrr = new_mrr
                # Recalculate net_mrr
                snapshot.net_mrr = new_mrr - snapshot.churned_mrr
                print(f'{month}: new_mrr {old_new_mrr:>12,.0f} -> {new_mrr:>12,.0f} kr, net_mrr = {snapshot.net_mrr:>12,.0f} kr')
            else:
                print(f'{month}: Snapshot not found in database')

        await session.commit()

    print('')
    print(f'[OK] Updated {len(updates)} monthly snapshots with New MRR')


if __name__ == "__main__":
    asyncio.run(main())
