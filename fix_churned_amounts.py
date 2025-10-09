"""
Script to fix churned customer amounts - normalize annual subscriptions to MRR
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from models.subscription import ChurnedCustomer, MonthlyMRRSnapshot


async def main():
    engine = create_async_engine('sqlite+aiosqlite:///data/app.db')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get all churned customers
        stmt = select(ChurnedCustomer).order_by(ChurnedCustomer.month, ChurnedCustomer.customer_name)
        result = await session.execute(stmt)
        all_churned = result.scalars().all()

        print(f'Total churned customer records: {len(all_churned)}')
        print('')

        updated_count = 0
        total_reduction = 0

        for customer in all_churned:
            # Check if plan name contains "(år)" or "(year)"
            if customer.plan_name and ('(år)' in customer.plan_name.lower() or '(year)' in customer.plan_name.lower()):
                old_amount = customer.amount
                new_amount = old_amount / 12
                reduction = old_amount - new_amount

                # Update the amount
                customer.amount = new_amount
                updated_count += 1
                total_reduction += reduction

                print(f'{customer.month} - {customer.customer_name:40s} {customer.plan_name:50s}')
                print(f'  Old: {old_amount:>10,.0f} kr -> New: {new_amount:>10,.0f} kr (reduction: {reduction:>10,.0f} kr)')

        print('')
        print(f'Updated {updated_count} records')
        print(f'Total MRR reduction: {total_reduction:,.0f} kr')

        # Commit the changes
        await session.commit()
        print('')
        print('[OK] Database updated')

        # Now recalculate monthly snapshot churned_mrr values
        print('')
        print('Recalculating monthly snapshot churned_mrr values...')

        stmt_snapshots = select(MonthlyMRRSnapshot).order_by(MonthlyMRRSnapshot.month)
        result_snapshots = await session.execute(stmt_snapshots)
        snapshots = result_snapshots.scalars().all()

        for snapshot in snapshots:
            # Get all churned customers for this month
            stmt_month_churn = select(ChurnedCustomer).where(ChurnedCustomer.month == snapshot.month)
            result_month = await session.execute(stmt_month_churn)
            month_churned = result_month.scalars().all()

            # Recalculate churned_mrr
            old_churned_mrr = snapshot.churned_mrr
            new_churned_mrr = sum(c.amount for c in month_churned)

            if old_churned_mrr != new_churned_mrr:
                snapshot.churned_mrr = new_churned_mrr
                # Recalculate net_mrr if we have new_mrr
                if snapshot.new_mrr:
                    snapshot.net_mrr = snapshot.new_mrr - new_churned_mrr

                print(f'{snapshot.month}: {old_churned_mrr:>12,.0f} kr -> {new_churned_mrr:>12,.0f} kr')

        await session.commit()
        print('')
        print('[OK] Monthly snapshots updated')


if __name__ == "__main__":
    asyncio.run(main())
