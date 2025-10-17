"""
Import Monthly Accounting Receivable Details

This script imports a single monthly Receivable Details report and updates the MRR snapshot.

Usage:
    python import_monthly_accounting.py <file_path>

Example:
    python import_monthly_accounting.py "excel/RD/Receivable Details oct 25.xlsx"
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta

from import_accounting_receivables import import_accounting_excel
from services.accounting import AccountingService
from database import AsyncSessionLocal


async def import_and_update_snapshot(file_path: str):
    """
    Import a monthly Receivable Details file and update its MRR snapshot

    Args:
        file_path: Path to the Excel file
    """
    print("\n" + "="*120)
    print("IMPORT MÅNEDLIG ACCOUNTING REPORT")
    print("="*120 + "\n")

    # Step 1: Import the Excel file
    print("[1/2] Importerer Excel-fil...")
    await import_accounting_excel(file_path)

    # Step 2: Get the source month from the import (we need to parse it again)
    filename = Path(file_path).stem.lower()

    month_map = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }

    source_month = None
    for month_abbr, month_num in month_map.items():
        if month_abbr in filename:
            # Try to find year
            import re
            year_match = re.search(r'\b(20)?(\d{2})\b', filename)
            if year_match:
                year = year_match.group(2)
                if len(year) == 2:
                    year = f"20{year}"
                source_month = f"{year}-{month_num}"
                break

    if not source_month:
        print(f"⚠️  Kunne ikke finne måned fra filnavn, bruker gjeldende måned")
        source_month = datetime.utcnow().strftime("%Y-%m")

    # Step 3: Generate MRR snapshot for this month
    print(f"\n[2/2] Genererer MRR snapshot for {source_month}...")

    async with AsyncSessionLocal() as session:
        service = AccountingService(session)
        snapshot = await service.generate_monthly_snapshot(source_month)

        print(f"\n✅ SNAPSHOT GENERERT:")
        print(f"   Måned:           {source_month}")
        print(f"   MRR:             {snapshot.mrr:,.0f} kr")
        print(f"   Kunder:          {snapshot.total_customers}")
        print(f"   Invoice items:   {snapshot.total_invoice_items}")
        print(f"   Credit notes:    {snapshot.total_creditnote_items}")

    print("\n" + "="*120)
    print("✅ IMPORT OG SNAPSHOT FULLFØRT")
    print("="*120)
    print(f"\nDu kan nå se resultatene på:")
    print(f"  - Dashboard:  http://localhost:8000/api/accounting/dashboard")
    print(f"  - Trender:    http://localhost:8000/api/accounting/trends")
    print(f"  - Drilldown:  http://localhost:8000/api/accounting/month-drilldown?month={source_month}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n" + "="*80)
        print("BRUK:")
        print("="*80)
        print()
        print("  python import_monthly_accounting.py <file_path>")
        print()
        print("Eksempel:")
        print('  python import_monthly_accounting.py "excel/RD/Receivable Details oct 25.xlsx"')
        print()
        print("Tips:")
        print("  - Plasser Excel-filen i excel/RD/ mappen")
        print("  - Filnavnet må inneholde månedsnavn (jan, feb, mar, etc) og år (24, 25, etc)")
        print("  - Scriptet vil automatisk:")
        print("    1. Importere data fra Excel-filen")
        print("    2. Slette eksisterende data for den måneden")
        print("    3. Generere nytt MRR snapshot")
        print()
        sys.exit(1)

    file_path = sys.argv[1]

    # Check if file exists
    if not Path(file_path).exists():
        print(f"\n❌ FEIL: Filen finnes ikke: {file_path}")
        print()
        sys.exit(1)

    # Run the import
    asyncio.run(import_and_update_snapshot(file_path))
