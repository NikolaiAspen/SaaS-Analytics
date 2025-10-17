"""
Analyze MRR gap between Subscriptions and Accounting for Summer 2025
Focus: Juni, Juli, September 2025
"""

import asyncio
from datetime import datetime
from sqlalchemy import select
from database import AsyncSessionLocal
from models.subscription import Subscription, MonthlyMRRSnapshot
from models.accounting import AccountingReceivableItem, AccountingMRRSnapshot
from services.accounting import AccountingService

async def analyze_summer_gap():
    print("\n" + "="*120)
    print("ANALYSE: SUBSCRIPTION vs ACCOUNTING MRR GAP - SOMMER 2025")
    print("="*120 + "\n")

    async with AsyncSessionLocal() as session:
        service = AccountingService(session)

        # Months to analyze
        months_to_analyze = ['2025-06', '2025-07', '2025-09']

        for target_month in months_to_analyze:
            print("\n" + "="*120)
            print(f"MÅNED: {target_month}")
            print("="*120 + "\n")

            # Get subscription snapshot
            stmt = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == target_month)
            result = await session.execute(stmt)
            sub_snapshot = result.scalar_one_or_none()

            # Get accounting snapshot
            stmt = select(AccountingMRRSnapshot).where(AccountingMRRSnapshot.month == target_month)
            result = await session.execute(stmt)
            acc_snapshot = result.scalar_one_or_none()

            if not sub_snapshot:
                print(f"⚠️  Ingen subscription snapshot for {target_month}")
                continue

            if not acc_snapshot:
                print(f"⚠️  Ingen accounting snapshot for {target_month}")
                continue

            # Show comparison
            print("SAMMENLIGNING:")
            print("-" * 80)
            print(f"Subscription MRR:  {sub_snapshot.mrr:>15,.0f} kr  ({sub_snapshot.total_customers} kunder)")
            print(f"Accounting MRR:    {acc_snapshot.mrr:>15,.0f} kr  ({acc_snapshot.total_customers} kunder)")
            print(f"Differanse:        {acc_snapshot.mrr - sub_snapshot.mrr:>+15,.0f} kr  ({((acc_snapshot.mrr - sub_snapshot.mrr) / sub_snapshot.mrr * 100):+.2f}%)")
            print()

            # Get accounting items breakdown by category
            year, month = map(int, target_month.split('-'))
            if month == 12:
                month_end = datetime(year + 1, 1, 1)
            else:
                month_end = datetime(year, month + 1, 1)
            from dateutil.relativedelta import relativedelta
            month_end = month_end - relativedelta(days=1)
            month_end = month_end.replace(hour=23, minute=59, second=59)

            # Get all accounting items active on last day of month
            stmt = select(AccountingReceivableItem).where(
                AccountingReceivableItem.period_start_date <= month_end,
                AccountingReceivableItem.period_end_date >= month_end
            )
            result = await session.execute(stmt)
            items = result.scalars().all()

            # Categorize
            by_category = {}
            recurring_total = 0
            non_recurring_total = 0

            for item in items:
                category = service.categorize_item(item.item_name)
                is_recurring = service.is_recurring_category(category)
                mrr = item.mrr_per_month or 0

                if category not in by_category:
                    by_category[category] = {
                        'mrr': 0,
                        'count': 0,
                        'is_recurring': is_recurring
                    }

                by_category[category]['mrr'] += mrr
                by_category[category]['count'] += 1

                if is_recurring:
                    recurring_total += mrr
                else:
                    non_recurring_total += mrr

            print("ACCOUNTING BREAKDOWN PER KATEGORI:")
            print("-" * 80)
            print(f"{'Kategori':<30} {'Type':<15} {'MRR':>15} {'Items':>10}")
            print("-" * 80)

            # Sort by MRR
            sorted_categories = sorted(by_category.items(), key=lambda x: abs(x[1]['mrr']), reverse=True)

            for cat_name, cat_data in sorted_categories:
                cat_type = "RECURRING" if cat_data['is_recurring'] else "ENGANGS"
                print(f"{cat_name:<30} {cat_type:<15} {cat_data['mrr']:>15,.0f} {cat_data['count']:>10}")

            print("-" * 80)
            print(f"{'RECURRING TOTAL':<30} {'':15} {recurring_total:>15,.0f}")
            print(f"{'ENGANGS TOTAL':<30} {'':15} {non_recurring_total:>15,.0f}")
            print(f"{'TOTAL':<30} {'':15} {recurring_total + non_recurring_total:>15,.0f}")
            print()

            # Check: Should recurring_total match acc_snapshot.mrr?
            if abs(recurring_total - acc_snapshot.mrr) > 1:
                print(f"⚠️  ADVARSEL: Recurring total ({recurring_total:,.0f}) matcher ikke snapshot MRR ({acc_snapshot.mrr:,.0f})")
                print(f"   Differanse: {recurring_total - acc_snapshot.mrr:+,.0f} kr")
            else:
                print(f"✅ Recurring total matcher snapshot MRR")

            print()

            # Get all live subscriptions for this month
            # Subscriptions don't have date filtering - they're just "live" at sync time
            # This is a fundamental limitation - we can't recreate historical subscription state
            print("SUBSCRIPTION DATA:")
            print("-" * 80)
            print(f"MRR:           {sub_snapshot.mrr:>15,.0f} kr")
            print(f"Kunder:        {sub_snapshot.total_customers:>15,}")
            print(f"ARPU:          {sub_snapshot.arpu:>15,.0f} kr")
            print()
            print("⚠️  Viktig: Subscription data er et snapshot fra sync-tidspunkt.")
            print("   Vi kan ikke filtrere subscriptions basert på historiske datoer.")
            print()

        # Summary
        print("\n" + "="*120)
        print("OPPSUMMERING:")
        print("="*120)
        print("""
MULIGE ÅRSAKER TIL GAP:

1. KREDITTNOTAER:
   Accounting inkluderer kredittnotaer (negative MRR), mens Subscriptions
   reflekterer live subscriptions uten hensyn til kredittnotaer.

2. PERIODISERING:
   - Accounting: Bruker faktiske fakturaperioder (start_date til end_date)
   - Subscriptions: Bruker subscription status (live/non_renewing)

3. TIMING:
   - Subscriptions opprettes, men fakturaer kan sendes senere
   - Fakturaperioder kan være forskjellige fra subscription-perioder

4. KATEGORISERING:
   - Accounting filtrerer bort ENGANGS-inntekter (Hardware, Andre inntekter)
   - Subscriptions inkluderer alle active subscriptions

5. MANGLENDE DATA:
   - Noen fakturaer kan være laget manuelt uten tilhørende subscription
   - Noen subscriptions kan eksistere uten at faktura er sendt ennå

NESTE STEG:
- Sjekk om det er store kredittnotaer i disse månedene
- Se om det er mange items kategorisert som "Andre inntekter" (burde vært recurring)
- Verifiser at category_mapping.json er oppdatert og korrekt
""")
        print("="*120 + "\n")

if __name__ == "__main__":
    asyncio.run(analyze_summer_gap())
