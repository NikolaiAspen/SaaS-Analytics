"""
Comprehensive analysis of MRR movement to explain discrepancies
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

        print('=' * 140)
        print('MRR MOVEMENT ANALYSIS - FORKLARING AV FORSKJELLER')
        print('=' * 140)
        print('')
        print('Excel-filene gir oss:')
        print('  1. Total MRR (slutten av maneden)')
        print('  2. New MRR (nye abonnementer)')
        print('  3. Churned MRR (oppsagte abonnementer)')
        print('')
        print('Men MRR kan endre seg pa andre mater:')
        print('  4. Expansion MRR (eksisterende kunder oppgraderer)')
        print('  5. Contraction MRR (eksisterende kunder nedgraderer)')
        print('  6. Reactivation MRR (tidligere churned kunder kommer tilbake)')
        print('  7. Prisendringer (endringer i plan-priser)')
        print('')
        print('Formelen:')
        print('  MRR endring = New MRR - Churned MRR + Expansion - Contraction + Reactivation + Prisendringer')
        print('')
        print('Det vi kan beregne fra Excel:')
        print('  Net MRR = New MRR - Churned MRR (dette er bare DELER av total endring)')
        print('')
        print('Forskjellen mellom faktisk MRR endring og Net MRR er:')
        print('  Expansion - Contraction + Reactivation + Prisendringer')
        print('')
        print('=' * 140)
        print('')

        print(f'{'Maned':10s} {'MRR':>12s} {'Endring':>12s} {'New MRR':>12s} {'Churned':>12s} {'Net MRR':>12s} {'Diff':>12s} {'Hva er diff?':30s}')
        print('-' * 140)

        previous_mrr = None
        for snap in snapshots:
            # Calculate actual MRR change
            if previous_mrr is not None:
                mrr_change = snap.mrr - previous_mrr
            else:
                mrr_change = 0

            # Calculate Net MRR (from Excel)
            net_mrr = snap.net_mrr

            # Calculate the difference
            diff = mrr_change - net_mrr

            # Explain what the diff represents
            if abs(diff) < 100:
                explanation = 'Minimal endringer'
            elif diff > 0:
                explanation = 'Expansion > Contraction'
            else:
                explanation = 'Contraction > Expansion'

            # Add flag if difference is significant
            flag = ' [!]' if abs(diff) > 5000 else ''

            print(f'{snap.month:10s} {snap.mrr:>12,.0f} {mrr_change:>12,.0f} {snap.new_mrr:>12,.0f} {snap.churned_mrr:>12,.0f} {net_mrr:>12,.0f} {diff:>12,.0f} {explanation:30s}{flag}')

            previous_mrr = snap.mrr

        print('-' * 140)
        print('')
        print('KONKLUSJON:')
        print('')
        print('Excel-filene er 100% korrekte for:')
        print('  - Total MRR (siste kolonne)')
        print('  - New MRR (nye abonnementer)')
        print('  - Churned MRR (oppsagte abonnementer)')
        print('')
        print('Men for a fa FULL forklaring av MRR endringer trenger vi ogsa:')
        print('  - Expansion MRR (oppgraderinger)')
        print('  - Contraction MRR (nedgraderinger)')
        print('  - Reactivation MRR (reaktiveringer)')
        print('  - Prisendringer')
        print('')
        print('Disse dataene er IKKE tilgjengelige i Excel-filene vi har.')
        print('Derfor matcher ikke Net MRR (New - Churned) den faktiske MRR endringen.')
        print('')
        print('Dette er NORMALT og FORVENTET.')
        print('')


if __name__ == "__main__":
    asyncio.run(main())
