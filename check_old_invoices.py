"""
Check for invoices dated before 2024-10-12 that affect October 2025 MRR
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from sqlalchemy import select


async def check_old_invoices():
    """Check for old invoices affecting October 2025"""

    cutoff_date = datetime(2024, 10, 12)
    target_month_start = datetime(2025, 10, 1)
    target_month_end = datetime(2025, 10, 31)

    async with AsyncSessionLocal() as session:
        # Query line items affecting October 2025
        query = (
            select(InvoiceLineItem, Invoice)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_start
            )
        )

        result = await session.execute(query)
        rows = result.all()

        # Separate by invoice date
        old_invoices = []
        new_invoices = []

        for line_item, invoice in rows:
            if invoice.invoice_date < cutoff_date:
                old_invoices.append((line_item, invoice))
            else:
                new_invoices.append((line_item, invoice))

        # Calculate MRR
        old_mrr = sum(li.mrr_per_month or 0 for li, inv in old_invoices)
        new_mrr = sum(li.mrr_per_month or 0 for li, inv in new_invoices)

        print("="*80)
        print("INVOICE DATE ANALYSIS FOR OCTOBER 2025 MRR")
        print("="*80)
        print(f"\nCutoff date: {cutoff_date.strftime('%Y-%m-%d')}")
        print(f"\nOLD invoices (before {cutoff_date.strftime('%Y-%m-%d')}):")
        print(f"  Line items: {len(old_invoices)}")
        print(f"  MRR impact: {old_mrr:,.2f} NOK")
        print(f"\nNEW invoices (from {cutoff_date.strftime('%Y-%m-%d')} onwards):")
        print(f"  Line items: {len(new_invoices)}")
        print(f"  MRR impact: {new_mrr:,.2f} NOK")
        print(f"\nTOTAL MRR: {old_mrr + new_mrr:,.2f} NOK")
        print(f"\nIf we exclude old invoices:")
        print(f"  Corrected MRR: {new_mrr:,.2f} NOK")
        print(f"  Difference: {old_mrr:,.2f} NOK ({(old_mrr/(old_mrr+new_mrr))*100:.1f}% of total)")

        # Show sample old invoices
        if old_invoices:
            print("\n" + "="*80)
            print(f"SAMPLE OLD INVOICES (first 20):")
            print("="*80)
            for i, (li, inv) in enumerate(old_invoices[:20], 1):
                print(f"{i:3d}. {inv.invoice_number:12s} | {inv.invoice_date.strftime('%Y-%m-%d')} | {inv.customer_name:30s} | {li.name:40s} | MRR: {li.mrr_per_month:10,.2f}")


if __name__ == "__main__":
    asyncio.run(check_old_invoices())
