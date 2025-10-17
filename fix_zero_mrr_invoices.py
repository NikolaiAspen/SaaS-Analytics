"""
Fix invoice line items with zero MRR despite having valid item_total and period_months
This script recalculates MRR for all affected invoices in Railway PostgreSQL
"""
import asyncio
import sys
from sqlalchemy import select, or_
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem

async def find_zero_mrr_items(dry_run=True):
    """
    Find and optionally fix invoice line items with zero/null MRR

    Args:
        dry_run: If True, only show what would be fixed without updating database
    """

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print("FIXING INVOICE LINE ITEMS WITH ZERO MRR")
        print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE UPDATE'}")
        print("Database: Railway PostgreSQL")
        print("=" * 80)

        # Find all invoice line items with zero or null MRR but positive item_total
        stmt = select(InvoiceLineItem, Invoice).join(
            Invoice, InvoiceLineItem.invoice_id == Invoice.id
        ).where(
            or_(
                InvoiceLineItem.mrr_per_month == 0,
                InvoiceLineItem.mrr_per_month.is_(None)
            ),
            InvoiceLineItem.item_total > 0,
            InvoiceLineItem.period_months > 0
        ).order_by(Invoice.invoice_number)

        result = await session.execute(stmt)
        items = result.all()

        if not items:
            print("\n[OK] No invoice line items found with zero MRR!")
            return

        print(f"\nFound {len(items)} invoice line items with zero/null MRR")
        print("\n" + "=" * 80)
        print("AFFECTED INVOICES:")
        print("=" * 80)

        fixes_to_apply = []

        for line_item, invoice in items:
            # Calculate correct MRR
            item_total = line_item.item_total or 0
            period_months = line_item.period_months or 1
            correct_mrr = item_total / period_months

            print(f"\nInvoice: {invoice.invoice_number}")
            print(f"  Customer: {invoice.customer_name}")
            print(f"  Product: {line_item.name}")
            print(f"  Period: {line_item.period_start_date} to {line_item.period_end_date}")
            print(f"  Period months: {period_months}")
            print(f"  Item total: {item_total} kr")
            print(f"  Current MRR: {line_item.mrr_per_month or 0} kr")
            print(f"  Correct MRR: {correct_mrr:.2f} kr")
            print(f"  Difference: +{correct_mrr:.2f} kr")

            fixes_to_apply.append({
                'line_item': line_item,
                'invoice': invoice,
                'new_mrr': correct_mrr
            })

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total invoices to fix: {len(fixes_to_apply)}")
        total_mrr_increase = sum(fix['new_mrr'] for fix in fixes_to_apply)
        print(f"Total MRR increase: {total_mrr_increase:.2f} kr")

        if dry_run:
            print("\n[DRY RUN] No changes were made to the database.")
            print("Run with --apply flag to apply these fixes.")
            return

        # Apply fixes
        print("\n" + "=" * 80)
        print("APPLYING FIXES...")
        print("=" * 80)

        for fix in fixes_to_apply:
            line_item = fix['line_item']
            invoice = fix['invoice']
            new_mrr = fix['new_mrr']

            # Update MRR
            line_item.mrr_per_month = new_mrr
            session.add(line_item)

            print(f"\n[UPDATED] Invoice {invoice.invoice_number}: MRR set to {new_mrr:.2f} kr")

        # Commit all changes
        await session.commit()

        print("\n" + "=" * 80)
        print("[SUCCESS] All fixes applied successfully!")
        print("=" * 80)
        print(f"Updated {len(fixes_to_apply)} invoice line items")
        print(f"Total MRR increase: {total_mrr_increase:.2f} kr")

        # Verify invoice 2010783 specifically
        print("\n" + "=" * 80)
        print("VERIFYING INVOICE 2010783")
        print("=" * 80)

        stmt = select(Invoice).where(Invoice.invoice_number == "2010783")
        result = await session.execute(stmt)
        invoice = result.scalar_one_or_none()

        if invoice:
            stmt = select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
            result = await session.execute(stmt)
            items = result.scalars().all()

            for item in items:
                print(f"\nProduct: {item.name}")
                print(f"  MRR: {item.mrr_per_month} kr")
                print(f"  Status: {'[OK]' if item.mrr_per_month > 0 else '[ERROR]'}")

async def main():
    """Main entry point"""
    # Check command line arguments
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        dry_run = False
        print("\n⚠️  WARNING: This will modify the Railway PostgreSQL database!")
        response = input("Are you sure you want to apply these fixes? (yes/no): ")
        if response.lower() != "yes":
            print("\nAborted.")
            return

    await find_zero_mrr_items(dry_run=dry_run)

if __name__ == "__main__":
    asyncio.run(main())
