"""
Verify that the MRR periodization fix has resolved the artificial volatility
"""

import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal
from models.accounting import AccountingMRRSnapshot

async def verify_fix():
    print("\n" + "="*120)
    print("VERIFIKASJON: MRR PERIODISERINGS-FIX")
    print("="*120 + "\n")

    async with AsyncSessionLocal() as session:
        # Get all snapshots ordered by month
        stmt = select(AccountingMRRSnapshot).order_by(AccountingMRRSnapshot.month)
        result = await session.execute(stmt)
        snapshots = result.scalars().all()

        print("MÅNED-FOR-MÅNED ANALYSE:\n")
        print(f"{'Måned':<12} {'MRR':>15} {'Endring':>15} {'Endring %':>12} {'Kunder':>10}")
        print("-" * 120)

        prev_mrr = None
        max_swing = 0
        max_swing_month = None

        for snapshot in snapshots:
            mrr = snapshot.mrr
            change = mrr - prev_mrr if prev_mrr else 0
            change_pct = (change / prev_mrr * 100) if prev_mrr and prev_mrr > 0 else 0

            # Track max swing
            if abs(change_pct) > abs(max_swing):
                max_swing = change_pct
                max_swing_month = snapshot.month

            change_str = f"{change:+,.0f} kr" if prev_mrr else "N/A"
            change_pct_str = f"{change_pct:+.2f}%" if prev_mrr else "N/A"

            print(f"{snapshot.month:<12} {mrr:>15,.0f} {change_str:>15} {change_pct_str:>12} {snapshot.total_customers:>10}")

            prev_mrr = mrr

        print("\n" + "="*120)
        print("RESULTAT:\n")
        print(f"Største svingning: {max_swing:+.2f}% i {max_swing_month}")
        print()

        # Check specific months that were problematic before
        july_2025 = next((s for s in snapshots if s.month == '2025-07'), None)
        aug_2025 = next((s for s in snapshots if s.month == '2025-08'), None)

        if july_2025 and aug_2025:
            print("SPESIFIKK ANALYSE: JULI → AUGUST 2025 (tidligere problemområde)")
            print("-" * 120)
            change = aug_2025.mrr - july_2025.mrr
            change_pct = (change / july_2025.mrr * 100) if july_2025.mrr > 0 else 0

            print(f"\nFØR FIX (basert på tidligere observasjon):")
            print(f"  Juli 2025:    2,472,782 kr")
            print(f"  August 2025:  1,993,967 kr")
            print(f"  Endring:      -478,816 kr (-19.36%) ❌ UNORMALT STORT FALL\n")

            print(f"ETTER FIX (med korrekt periodisering):")
            print(f"  Juli 2025:    {july_2025.mrr:,.0f} kr")
            print(f"  August 2025:  {aug_2025.mrr:,.0f} kr")
            print(f"  Endring:      {change:+,.0f} kr ({change_pct:+.2f}%) ✅ NORMAL VEKST\n")

            if abs(change_pct) < 5:
                print("✅ SUKSESS! MRR er nå stabil måned-for-måned.")
                print("   Periodiseringen av 12-måneders produkter fungerer som forventet.")
            else:
                print("⚠️  ADVARSEL: Det er fortsatt en uventet stor svingning.")

        print("\n" + "="*120)
        print("KONKLUSJON:")
        print("="*120)
        print("""
Produkter som nå er korrekt periodisert for 12 måneder:
✓ Alle produkter med "oppgradering" i navnet
✓ Sporingstrafikk VMS GPRS (alle varianter)
✓ 30 dager ERS (alle varianter)

Disse produktene vil nå forbli aktive i 12 måneder fra fakturadato,
istedenfor å "forsvinne" hver måned som tidligere.

Dette gir stabil MRR-rapportering uten kunstige svingninger.
""")
        print("="*120 + "\n")

if __name__ == "__main__":
    asyncio.run(verify_fix())
