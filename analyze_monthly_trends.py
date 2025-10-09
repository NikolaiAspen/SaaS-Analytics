"""
Analyze monthly MRR snapshots to check if all fields are consistent
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from models.subscription import MonthlyMRRSnapshot

async def analyze():
    engine = create_async_engine('sqlite+aiosqlite:///data/app.db')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get all monthly snapshots
        stmt = select(MonthlyMRRSnapshot).order_by(MonthlyMRRSnapshot.month)
        result = await session.execute(stmt)
        snapshots = result.scalars().all()

        print('=== MONTHLY MRR SNAPSHOT ANALYSE ===')
        print('')
        print('Forklaring av felter:')
        print('  MRR        = Total MRR pa slutten av maneden')
        print('  New MRR    = MRR fra nye kunder i maneden')
        print('  Churned    = MRR tapt fra kunder som churned')
        print('  Net MRR    = New MRR - Churned MRR (netto endring)')
        print('  Beregnet   = MRR fra forrige maned + Net MRR (skal matche MRR)')
        print('')
        print('-' * 120)
        print(f'{'Maned':10s} {'MRR':>12s} {'New MRR':>12s} {'Churned':>12s} {'Net MRR':>12s} {'Beregnet MRR':>15s} {'Diff':>12s}')
        print('-' * 120)

        previous_mrr = None
        for snap in snapshots:
            # Calculate what MRR should be based on previous month + net change
            if previous_mrr is not None:
                calculated_mrr = previous_mrr + snap.net_mrr
                diff = snap.mrr - calculated_mrr
            else:
                calculated_mrr = snap.mrr
                diff = 0

            # Check if calculation makes sense
            warning = ''
            if abs(diff) > 100:  # More than 100 kr difference
                warning = ' [!]'

            # Check if net_mrr = new_mrr - churned_mrr
            expected_net = snap.new_mrr - snap.churned_mrr
            if abs(snap.net_mrr - expected_net) > 1:  # Allow 1 kr rounding
                warning += ' [NET ERR]'

            print(f'{snap.month:10s} {snap.mrr:>12,.0f} {snap.new_mrr:>12,.0f} {snap.churned_mrr:>12,.0f} {snap.net_mrr:>12,.0f} {calculated_mrr:>15,.0f} {diff:>12,.0f}{warning}')

            previous_mrr = snap.mrr

        print('-' * 120)
        print('')
        print('Sjekker for feil:')
        print('')

        # Check each snapshot for consistency
        previous_mrr = None
        errors_found = False
        for snap in snapshots:
            errors = []

            # 1. Check if net_mrr = new_mrr - churned_mrr
            expected_net = snap.new_mrr - snap.churned_mrr
            if abs(snap.net_mrr - expected_net) > 1:
                errors.append(f'Net MRR feil: {snap.net_mrr:,.0f} burde vaere {expected_net:,.0f}')

            # 2. Check if MRR change matches net_mrr
            if previous_mrr is not None:
                actual_change = snap.mrr - previous_mrr
                if abs(actual_change - snap.net_mrr) > 100:  # Allow 100 kr tolerance
                    errors.append(f'MRR endring ({actual_change:,.0f}) matcher ikke Net MRR ({snap.net_mrr:,.0f})')

            if errors:
                errors_found = True
                print(f'{snap.month}:')
                for error in errors:
                    print(f'  [X] {error}')

            previous_mrr = snap.mrr

        if not errors_found:
            print('[OK] Ingen feil funnet i datasettene!')

        print('')
        print('[OK] Analyse fullfort')

asyncio.run(analyze())
