"""
Import invoices from Zoho Invoice CSV export

This script imports invoices from the Zoho Invoice CSV export format
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from services.invoice import InvoiceService
from sqlalchemy import delete


async def import_from_csv():
    """Import invoices from CSV file"""

    print("=== INVOICE IMPORT FROM CSV ===\n")

    # File path
    csv_file = "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (4).csv"

    # Read CSV
    print("Step 1: Loading invoice data from CSV...")
    df = pd.read_csv(csv_file)
    print(f"  [OK] Loaded {len(df)} line items")
    print()

    # Parse dates
    df['Invoice Date'] = pd.to_datetime(df['Invoice Date'], errors='coerce')
    df['Due Date'] = pd.to_datetime(df['Due Date'], errors='coerce')

    print(f"  Date range: {df['Invoice Date'].min()} to {df['Invoice Date'].max()}")
    print(f"  Unique invoices: {df['Invoice ID'].nunique()}")
    print(f"  Unique customers: {df['Customer ID'].nunique()}")
    print()

    # Import to database
    print("Step 2: Importing to database...")

    async with AsyncSessionLocal() as session:
        invoice_service = InvoiceService(session)

        # Clear existing invoices
        print("  Clearing existing invoices...")
        await session.execute(delete(InvoiceLineItem))
        await session.execute(delete(Invoice))
        await session.commit()
        print("  [OK] Cleared existing data")
        print()

        # Group by Invoice ID
        grouped = df.groupby('Invoice ID')
        total_invoices = len(grouped)

        print(f"  Processing {total_invoices} invoices...")

        imported_count = 0
        skipped_count = 0

        for invoice_id, line_items in grouped:
            try:
                # Get invoice header info from first line item
                first_item = line_items.iloc[0]

                # Parse dates
                def parse_date(date_val):
                    if pd.isna(date_val):
                        return None
                    if isinstance(date_val, datetime):
                        return date_val.replace(tzinfo=None)
                    return pd.to_datetime(date_val).replace(tzinfo=None)

                invoice_date = parse_date(first_item['Invoice Date'])
                due_date = parse_date(first_item['Due Date'])

                # Create Invoice
                invoice = Invoice(
                    id=str(invoice_id),
                    invoice_number=str(first_item['Invoice Number']),
                    invoice_date=invoice_date,
                    due_date=due_date,
                    customer_id=str(first_item['Customer ID']),
                    customer_name=str(first_item['Customer Name']),
                    customer_email="",  # Not in CSV
                    currency_code=str(first_item.get('Currency Code', 'NOK')),
                    sub_total=float(first_item.get('SubTotal', 0)),
                    tax_total=0.0,  # Calculate from line items if needed
                    total=float(first_item.get('Total', 0)),
                    balance=float(first_item.get('Balance', 0)),
                    status=str(first_item.get('Invoice Status', 'sent')).lower(),
                    transaction_type='invoice',
                    created_time=invoice_date,
                    updated_time=invoice_date,
                )
                session.add(invoice)

                # Process line items
                for _, item_row in line_items.iterrows():
                    # Get item details
                    item_name = item_row.get('Item Name', '')
                    item_desc = item_row.get('Item Desc', '')

                    # Parse price and quantity
                    price = float(item_row.get('Item Price', 0))
                    quantity = int(item_row.get('Quantity', 1))
                    item_total = float(item_row.get('Item Total', price * quantity))

                    # Calculate MRR from description
                    mrr_calc = invoice_service.calculate_mrr_from_line_item({
                        'description': item_desc,
                        'price': price
                    })

                    # Create line item
                    line_item = InvoiceLineItem(
                        invoice_id=str(invoice_id),
                        item_id=str(item_row.get('Item ID', '')),
                        product_id='',  # Not in this CSV format
                        subscription_id=str(item_row.get('Subscription ID', '') if pd.notna(item_row.get('Subscription ID')) else ''),
                        name=str(item_name) if pd.notna(item_name) else str(item_desc),
                        description=str(item_desc) if pd.notna(item_desc) else '',
                        code=str(item_row.get('Item Code', '')),
                        unit='',
                        price=price,
                        quantity=quantity,
                        item_total=item_total,
                        tax_percentage=float(item_row.get('Item Tax %', 0)),
                        tax_name=str(item_row.get('Item Tax', '')),
                        period_start_date=mrr_calc['period_start_date'],
                        period_end_date=mrr_calc['period_end_date'],
                        period_months=mrr_calc['period_months'],
                        mrr_per_month=mrr_calc['mrr_per_month'],
                    )
                    session.add(line_item)

                imported_count += 1

                # Commit every 100 invoices
                if imported_count % 100 == 0:
                    await session.commit()
                    print(f"    Progress: {imported_count}/{total_invoices} invoices ({(imported_count/total_invoices)*100:.1f}%)")

            except Exception as e:
                print(f"    [ERROR] Error importing invoice {invoice_id}: {e}")
                skipped_count += 1
                continue

        # Final commit
        await session.commit()
        print(f"  [OK] Imported {imported_count} invoices")
        print(f"  [SKIPPED] {skipped_count} invoices due to errors")
        print()

        # Step 3: Generate monthly snapshots
        print("Step 3: Generating monthly MRR snapshots...")

        today = datetime.utcnow()
        from dateutil.relativedelta import relativedelta

        snapshots_created = []
        for i in range(24):  # Last 24 months
            month_date = today - relativedelta(months=i)
            month_str = month_date.strftime("%Y-%m")

            try:
                snapshot = await invoice_service.generate_monthly_snapshot(month_str)
                snapshots_created.append(month_str)
                print(f"  [OK] {month_str}: MRR = {snapshot.mrr:,.2f} NOK, Customers = {snapshot.total_customers}")
            except Exception as e:
                print(f"  [ERROR] Failed to create snapshot for {month_str}: {e}")

        print()
        print(f"[OK] Generated {len(snapshots_created)} monthly snapshots")

    print()
    print("=== IMPORT COMPLETE ===")
    print(f"Total invoices imported: {imported_count}")
    print(f"Total snapshots generated: {len(snapshots_created)}")


if __name__ == "__main__":
    asyncio.run(import_from_csv())
