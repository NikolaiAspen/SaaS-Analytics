"""
Fix net_mrr calculation in all monthly snapshots
Net MRR should = New MRR - Churned MRR
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from models.subscription import MonthlyMRRSnapshot


async def main():
    engine = create_async_engine('sqlite+aiosqlite:///data/app.db')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get all monthly snapshots
        stmt = select(MonthlyMRRSnapshot).order_by(MonthlyMRRSnapshot.month)
        result = await session.execute(stmt)
        snapshots = result.scalars().all()

        print('Fixing net_mrr calculations...')
        print('')

        updated_count = 0
        for snap in snapshots:
            # Calculate what net_mrr should be
            correct_net_mrr = snap.new_mrr - snap.churned_mrr

            # Check if it needs updating
            if abs(snap.net_mrr - correct_net_mrr) > 0.01:  # More than 1 cent difference
                print(f'{snap.month}: {snap.net_mrr:>12,.0f} -> {correct_net_mrr:>12,.0f}')
                snap.net_mrr = correct_net_mrr
                updated_count += 1

        await session.commit()

        print('')
        print(f'[OK] Updated {updated_count} monthly snapshots')


if __name__ == "__main__":
    asyncio.run(main())
