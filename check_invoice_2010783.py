"""
Check invoice 2010783 and its credit note
"""
import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem, CreditNote, CreditNoteLineItem
from datetime import datetime

async def check_invoice():
    """Check invoice 2010783 details"""

    invoice_number = "2010783"

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print(f"CHECKING INVOICE {invoice_number}")
        print("=" * 80)

        # Get invoice
        stmt = select(Invoice).where(Invoice.invoice_number == invoice_number)
        result = await session.execute(stmt)
        invoice = result.scalar_one_or_none()

        if not invoice:
            print(f"Invoice {invoice_number} not found!")
            return

        print(f"\nInvoice ID: {invoice.id}")
        print(f"Customer: {invoice.customer_name}")
        print(f"Date: {invoice.invoice_date}")
        print(f"Type: {invoice.transaction_type}")

        # Get line items
        stmt = select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
        result = await session.execute(stmt)
        line_items = result.scalars().all()

        print(f"\n--- LINE ITEMS ({len(line_items)}) ---")
        for item in line_items:
            print(f"\nProduct: {item.name}")
            print(f"  Period: {item.period_start_date} to {item.period_end_date}")
            print(f"  Period months: {item.period_months}")
            print(f"  Item total: {item.item_total}")
            print(f"  MRR per month: {item.mrr_per_month}")

            # Check if active in September
            sept_start = datetime(2025, 9, 1)
            sept_end = datetime(2025, 9, 30)
            is_active = (item.period_start_date <= sept_end and
                        item.period_end_date >= sept_start)
            print(f"  Active in Sept 2025: {is_active}")

        # Check for credit notes
        stmt = select(CreditNote).where(CreditNote.invoice_id == invoice.id)
        result = await session.execute(stmt)
        credit_notes = result.scalars().all()

        if credit_notes:
            print(f"\n--- CREDIT NOTES ({len(credit_notes)}) ---")
            for cn in credit_notes:
                print(f"\nCredit Note: {cn.creditnote_number}")
                print(f"  Date: {cn.creditnote_date}")
                print(f"  Status: {cn.status}")

                # Get credit note line items
                stmt = select(CreditNoteLineItem).where(
                    CreditNoteLineItem.creditnote_id == cn.id
                )
                result = await session.execute(stmt)
                cn_items = result.scalars().all()

                print(f"  Line items: {len(cn_items)}")
                for cn_item in cn_items:
                    print(f"\n  Product: {cn_item.name}")
                    print(f"    Period: {cn_item.period_start_date} to {cn_item.period_end_date}")
                    print(f"    Period months: {cn_item.period_months}")
                    print(f"    Item total: {cn_item.item_total}")
                    print(f"    MRR per month: {cn_item.mrr_per_month}")

                    # Check if active in September
                    is_active = (cn_item.period_start_date <= sept_end and
                                cn_item.period_end_date >= sept_start)
                    print(f"    Active in Sept 2025: {is_active}")

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        total_invoice_mrr = sum(item.mrr_per_month or 0 for item in line_items)
        print(f"Invoice MRR (Sept 2025): {total_invoice_mrr}")

        if credit_notes:
            for cn in credit_notes:
                stmt = select(CreditNoteLineItem).where(
                    CreditNoteLineItem.creditnote_id == cn.id
                )
                result = await session.execute(stmt)
                cn_items = result.scalars().all()
                total_cn_mrr = sum(item.mrr_per_month or 0 for item in cn_items)
                print(f"Credit Note MRR (Sept 2025): {total_cn_mrr}")

        print(f"\nExpected net MRR: 0 (invoice + credit note should cancel)")

if __name__ == "__main__":
    asyncio.run(check_invoice())
