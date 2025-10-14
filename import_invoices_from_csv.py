"""
Import invoices from Invoice CSV files to database

This script imports invoice data from Zoho Invoice CSV exports with explicit start/end dates
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from services.invoice import InvoiceService
from sqlalchemy import delete


async def import_invoices_from_csv():
    """Import invoices from Invoice CSV files"""

    print("=== INVOICE IMPORT FROM CSV ===\n")

    # Invoice CSV files to import (ALL 2024-2025 data)
    invoice_files = [
        "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (3).csv",  # Jan-Jun 2024
        "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (2).csv",  # Jul-Dec 2024
        "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (4).csv",  # Jan-Apr 2025
        "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice.csv",      # May-Oct 2025
    ]

    # Credit Note CSV file
    creditnote_file = "c:/Users/nikolai/Code/Saas_analyse/excel/Credit_Note.csv"

    async with AsyncSessionLocal() as session:
        invoice_service = InvoiceService(session)

        # Clear existing invoices
        print("Step 1: Clearing existing invoices...")
        await session.execute(delete(InvoiceLineItem))
        await session.execute(delete(Invoice))
        await session.commit()
        print("  [OK] Cleared existing data\n")

        total_invoices_imported = 0
        total_lines_imported = 0

        for csv_file in csv_files:
            print(f"Step 2: Loading {csv_file.split('/')[-1]}...")
            try:
                df = pd.read_csv(csv_file)
                print(f"  [OK] Loaded {len(df)} line items\n")
            except Exception as e:
                print(f"  [ERROR] Failed to load: {e}\n")
                continue

            # Group by Invoice ID
            grouped = df.groupby('Invoice ID')
            print(f"Step 3: Processing {len(grouped)} invoices...")

            for invoice_id, lines in grouped:
                try:
                    # Get invoice header from first line
                    first = lines.iloc[0]

                    # Parse dates
                    def parse_date(date_val):
                        if pd.isna(date_val):
                            return None
                        if isinstance(date_val, datetime):
                            return date_val.replace(tzinfo=None)
                        try:
                            return pd.to_datetime(date_val).replace(tzinfo=None)
                        except:
                            return None

                    invoice_date = parse_date(first['Invoice Date'])
                    due_date = parse_date(first['Due Date'])

                    # Skip if no invoice date
                    if not invoice_date:
                        continue

                    # Create Invoice
                    invoice = Invoice(
                        id=str(invoice_id),
                        invoice_number=str(first['Invoice Number']),
                        invoice_date=invoice_date,
                        due_date=due_date,
                        customer_id=str(first['Customer ID']),
                        customer_name=str(first['Customer Name']),
                        customer_email="",
                        currency_code=str(first.get('Currency Code', 'NOK')),
                        sub_total=float(first.get('SubTotal', 0)),
                        tax_total=0.0,  # Not directly in CSV
                        total=float(first.get('Total', 0)),
                        balance=float(first.get('Balance', 0)),
                        status=str(first.get('Invoice Status', 'sent')).lower(),
                        transaction_type='invoice',
                        created_time=invoice_date,
                        updated_time=invoice_date,
                    )
                    session.add(invoice)

                    # Process line items
                    for _, item_row in lines.iterrows():
                        # Skip non-product lines
                        line_type = str(item_row.get('Line Item Type', '')).lower()
                        if line_type in ['shipping_charge', 'discount', 'adjustment']:
                            continue

                        # Get item details
                        item_name = str(item_row.get('Item Name', ''))
                        item_desc = str(item_row.get('Item Desc', ''))
                        item_price = float(item_row.get('Item Price', 0))
                        quantity = int(item_row.get('Quantity', 1))
                        item_total = float(item_row.get('Item Total', 0))

                        # Parse period dates (explicit in CSV!)
                        start_date = parse_date(item_row.get('Start Date'))
                        end_date = parse_date(item_row.get('End Date'))

                        # Calculate period months
                        if start_date and end_date:
                            months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                            if end_date.day >= start_date.day:
                                months += 1
                            months = max(1, months)
                        else:
                            months = 1

                        # Calculate MRR per month
                        mrr_per_month = item_price / months if months > 0 else item_price

                        # Get tax info
                        tax_percentage = float(item_row.get('Item Tax %', 0))
                        tax_name = str(item_row.get('Item Tax', ''))

                        # Create line item
                        line_item = InvoiceLineItem(
                            invoice_id=str(invoice_id),
                            item_id=str(item_row.get('Item ID', '')),
                            product_id=str(item_row.get('Item ID', '')),
                            subscription_id=str(item_row.get('Subscription ID', '')),
                            name=item_name,
                            description=item_desc,
                            code=str(item_row.get('Item Code', '')),
                            unit='',
                            price=item_price,
                            quantity=quantity,
                            item_total=item_total,
                            tax_percentage=tax_percentage,
                            tax_name=tax_name,
                            period_start_date=start_date,
                            period_end_date=end_date,
                            period_months=months,
                            mrr_per_month=mrr_per_month,
                        )
                        session.add(line_item)
                        total_lines_imported += 1

                    total_invoices_imported += 1

                    # Commit every 100 invoices
                    if total_invoices_imported % 100 == 0:
                        await session.commit()
                        print(f"    Progress: {total_invoices_imported} invoices, {total_lines_imported} line items")

                except Exception as e:
                    print(f"    [ERROR] Error importing invoice {invoice_id}: {e}")
                    continue

            # Commit after each file
            await session.commit()
            print(f"  [OK] Completed {csv_file.split('/')[-1]}\n")

        print(f"\nStep 4: Generating monthly MRR snapshots...")
        from dateutil.relativedelta import relativedelta

        today = datetime.utcnow()
        snapshots_created = []

        # Generate snapshots for last 36 months (to cover all imported data)
        for i in range(36):
            month_date = today - relativedelta(months=i)
            month_str = month_date.strftime("%Y-%m")

            try:
                snapshot = await invoice_service.generate_monthly_snapshot(month_str)
                if snapshot.mrr > 0:  # Only count months with actual data
                    snapshots_created.append(month_str)
                    print(f"  [OK] {month_str}: MRR = {snapshot.mrr:,.2f} NOK, Customers = {snapshot.total_customers}")
            except Exception as e:
                # Skip months without data
                pass

        print()
        print("=== IMPORT COMPLETE ===")
        print(f"Total invoices imported: {total_invoices_imported}")
        print(f"Total line items imported: {total_lines_imported}")
        print(f"Total snapshots generated: {len(snapshots_created)}")


if __name__ == "__main__":
    asyncio.run(import_invoices_from_csv())
