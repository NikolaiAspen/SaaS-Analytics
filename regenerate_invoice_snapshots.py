"""
Regenerate invoice MRR snapshots for the last 12 months
Uses the updated month-end snapshot logic from services/invoice.py
"""
import asyncio
from datetime import datetime
from dateutil.relativedelta import relativedelta
from database import AsyncSessionLocal
from services.invoice import InvoiceService

def safe_print(message):
    """Print with ASCII-safe characters for Windows console"""
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        print(message.encode('ascii', errors='replace').decode('ascii'), flush=True)

async def regenerate_snapshots():
    """Regenerate invoice MRR snapshots for the last 12 months"""
    safe_print("=" * 80)
    safe_print("REGENERATING INVOICE MRR SNAPSHOTS (Month-End Logic)")
    safe_print("=" * 80)

    async with AsyncSessionLocal() as session:
        invoice_service = InvoiceService(session)

        today = datetime.utcnow()
        snapshots_created = []

        safe_print(f"\nGenerating snapshots for last 12 months...\n")

        for i in range(12):
            month_date = today - relativedelta(months=i)
            month_str = month_date.strftime("%Y-%m")

            try:
                # This will use the updated month-end logic
                await invoice_service.generate_monthly_snapshot(month_str)
                snapshots_created.append(month_str)
                safe_print(f"  ✓ {month_str}")
            except Exception as e:
                safe_print(f"  ✗ {month_str}: {e}")

        safe_print(f"\n✓ Successfully regenerated {len(snapshots_created)} snapshots")
        safe_print("=" * 80)

if __name__ == "__main__":
    asyncio.run(regenerate_snapshots())
