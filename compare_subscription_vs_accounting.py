"""
Compare Subscription MRR vs Accounting MRR

This helps identify why there's a difference between:
- Subscription-based MRR (from Zoho Subscriptions API)
- Accounting-based MRR (from Receivable Details Excel files)
"""

import asyncio
from datetime import datetime
from sqlalchemy import select, func
from database import AsyncSessionLocal
from models.subscription import MonthlyMRRSnapshot
from models.accounting import AccountingMRRSnapshot

async def compare_mrr_sources():
    print("\n" + "="*120)
    print("SAMMENLIGNING: SUBSCRIPTION MRR vs ACCOUNTING MRR")
    print("="*120 + "\n")

    async with AsyncSessionLocal() as session:
        # Get subscription snapshots
        stmt_sub = select(MonthlyMRRSnapshot).order_by(MonthlyMRRSnapshot.month)
        result = await session.execute(stmt_sub)
        sub_snapshots = result.scalars().all()

        # Get accounting snapshots
        stmt_acc = select(AccountingMRRSnapshot).order_by(AccountingMRRSnapshot.month)
        result = await session.execute(stmt_acc)
        acc_snapshots = result.scalars().all()

        # Create lookup dicts
        sub_by_month = {s.month: s for s in sub_snapshots}
        acc_by_month = {s.month: s for s in acc_snapshots}

        # Find common months
        all_months = sorted(set(sub_by_month.keys()) | set(acc_by_month.keys()))

        print("MÅNED-FOR-MÅNED SAMMENLIGNING:\n")
        print(f"{'Måned':<12} {'Subscription MRR':>20} {'Accounting MRR':>20} {'Differanse':>20} {'Diff %':>12}")
        print("-" * 120)

        total_sub = 0
        total_acc = 0
        months_compared = 0

        for month in all_months:
            sub = sub_by_month.get(month)
            acc = acc_by_month.get(month)

            if sub and acc:
                sub_mrr = sub.mrr
                acc_mrr = acc.mrr
                diff = acc_mrr - sub_mrr
                diff_pct = (diff / sub_mrr * 100) if sub_mrr > 0 else 0

                total_sub += sub_mrr
                total_acc += acc_mrr
                months_compared += 1

                print(f"{month:<12} {sub_mrr:>20,.0f} {acc_mrr:>20,.0f} {diff:>+20,.0f} {diff_pct:>+11.2f}%")
            elif sub:
                print(f"{month:<12} {sub.mrr:>20,.0f} {'N/A':>20} {'N/A':>20} {'N/A':>12}")
            elif acc:
                print(f"{month:<12} {'N/A':>20} {acc.mrr:>20,.0f} {'N/A':>20} {'N/A':>12}")

        print("-" * 120)
        if months_compared > 0:
            avg_sub = total_sub / months_compared
            avg_acc = total_acc / months_compared
            avg_diff = avg_acc - avg_sub
            avg_diff_pct = (avg_diff / avg_sub * 100) if avg_sub > 0 else 0

            print(f"{'GJENNOMSNITT':<12} {avg_sub:>20,.0f} {avg_acc:>20,.0f} {avg_diff:>+20,.0f} {avg_diff_pct:>+11.2f}%")

        print("\n" + "="*120)
        print("MULIGE ÅRSAKER TIL FORSKJELLER:")
        print("="*120)
        print("""
1. TIMING-FORSKJELLER:
   - Subscriptions opprettes, men fakturaer sendes senere
   - Fakturaperioder kan avvike fra subscription-perioder

2. ENGANGSKOSTNADER (inkludert i Accounting, ikke i Subscriptions):
   - Hardware
   - Oppgraderinger
   - Andre engangsgebyrer

3. KREDITTNOTAER:
   - Accounting inkluderer kredittnotaer (negative verdier)
   - Subscriptions reflekterer ikke alltid kredittnotaer umiddelbart

4. PERIODISERING:
   - Subscriptions: Basert på subscription status (live, non_renewing)
   - Accounting: Basert på faktiske fakturaperioder med periodisering

5. KATEGORISERING:
   - Accounting filtrerer bort ikke-recurring inntekter (Hardware, Andre inntekter)
   - Subscriptions inkluderer alle active subscriptions
""")

        # Let's analyze specific months in detail
        print("\n" + "="*120)
        print("DETALJERT ANALYSE: SISTE MÅNED MED DATA FRA BEGGE KILDER")
        print("="*120 + "\n")

        # Find latest common month
        common_months = [m for m in all_months if m in sub_by_month and m in acc_by_month]
        if common_months:
            latest_month = common_months[-1]
            sub = sub_by_month[latest_month]
            acc = acc_by_month[latest_month]

            print(f"Måned: {latest_month}\n")

            print("SUBSCRIPTION-BASERT (fra Zoho Subscriptions API):")
            print(f"  MRR:           {sub.mrr:>15,.0f} kr")
            print(f"  Kunder:        {sub.total_customers:>15,}")
            print(f"  ARPU:          {sub.arpu:>15,.0f} kr")
            print()

            print("ACCOUNTING-BASERT (fra Receivable Details):")
            print(f"  MRR:           {acc.mrr:>15,.0f} kr")
            print(f"  Kunder:        {acc.total_customers:>15,}")
            print(f"  ARPU:          {acc.arpu:>15,.0f} kr")
            print(f"  Invoice items: {acc.total_invoice_items:>15,}")
            print(f"  Credit notes:  {acc.total_creditnote_items:>15,}")
            print()

            diff = acc.mrr - sub.mrr
            diff_pct = (diff / sub.mrr * 100) if sub.mrr > 0 else 0

            print("DIFFERANSE:")
            print(f"  MRR diff:      {diff:>+15,.0f} kr ({diff_pct:+.2f}%)")
            print(f"  Kunder diff:   {acc.total_customers - sub.total_customers:>+15,}")

        print("\n" + "="*120)
        print("NESTE STEG FOR Å FORSTÅ FORSKJELLENE:")
        print("="*120)
        print("""
1. Sjekk om Accounting MRR inkluderer engangs-inntekter som burde vært filtrert bort
2. Verifiser at kategoriseringen i services/accounting.py er korrekt
3. Sjekk om det er store kredittnotaer som påvirker Accounting MRR
4. Sammenlign kundelist fra Subscriptions vs Accounting for samme måned
5. Se på items som er i Accounting men ikke i Subscriptions (og vice versa)
""")
        print("="*120 + "\n")

if __name__ == "__main__":
    asyncio.run(compare_mrr_sources())
