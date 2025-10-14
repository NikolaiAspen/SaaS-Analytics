"""
Check if there are invoice customers named exactly as Niko reported
"""

import asyncio
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from sqlalchemy import select, func
from datetime import datetime


async def check_invoice_customers():
    """Check invoice customer names for September 2025"""

    target_names = [
        'TALBOR AS',
        'NUTRIMAR HARVEST AS',
        'SVERRE JOHANSEN',
        'BRØDRENE BÆKKEN AS',
        'MAGNE KLAUDIUSSEN'
    ]

    target_start = datetime(2025, 9, 1)
    target_end = datetime(2025, 9, 30)

    async with AsyncSessionLocal() as session:
        print("="*100)
        print("CHECKING INVOICE CUSTOMER NAMES FOR SEPTEMBER 2025")
        print("="*100)

        for customer_name in target_names:
            print(f"\n{customer_name}")
            print("-"*100)

            # Check for invoices with this exact customer name
            stmt = select(InvoiceLineItem, Invoice).join(
                Invoice, InvoiceLineItem.invoice_id == Invoice.id
            ).where(
                Invoice.customer_name == customer_name,
                InvoiceLineItem.period_start_date <= target_end,
                InvoiceLineItem.period_end_date >= target_start
            )
            result = await session.execute(stmt)
            invoice_rows = result.all()

            if invoice_rows:
                print(f"  FOUND {len(invoice_rows)} invoice line items:")
                total_mrr = 0
                for line_item, invoice in invoice_rows:
                    mrr = line_item.mrr_per_month or 0
                    total_mrr += mrr
                    print(f"    - Invoice: {invoice.invoice_number}")
                    print(f"      Item: {line_item.name}")
                    print(f"      MRR: {mrr:.2f} kr")
                    print(f"      Vessel: {getattr(line_item, 'vessel_name', 'N/A')}")
                    print(f"      Call Sign: {getattr(line_item, 'call_sign', 'N/A')}")
                print(f"  TOTAL MRR: {total_mrr:.2f} kr")
            else:
                print(f"  NO INVOICES FOUND with exact customer name")

                # Try case-insensitive search
                stmt = select(Invoice.customer_name, func.sum(InvoiceLineItem.mrr_per_month)).join(
                    InvoiceLineItem, Invoice.id == InvoiceLineItem.invoice_id
                ).where(
                    func.lower(Invoice.customer_name).like(f"%{customer_name.lower()[:10]}%"),
                    InvoiceLineItem.period_start_date <= target_end,
                    InvoiceLineItem.period_end_date >= target_start
                ).group_by(Invoice.customer_name)
                result = await session.execute(stmt)
                similar_names = result.all()

                if similar_names:
                    print(f"  Similar names found:")
                    for name, total_mrr in similar_names:
                        print(f"    - {name}: {total_mrr:.2f} kr MRR")


if __name__ == "__main__":
    asyncio.run(check_invoice_customers())
