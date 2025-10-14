"""
Import complete invoice data from NEW CSV files (2024-2025)
Covers: Jan-Jun 2024, Jul-Dec 2024, Jan-Jun 2025, Jul-Oct 2025
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from services.invoice import InvoiceService
from sqlalchemy import delete


# Hardware/one-time product codes to exclude
HARDWARE_CODES = {
    'Fangstr VMS', 'Fangstr Connect', 'Vertikal/Horisontal stålfeste',
    'Frakt', 'Fraktkostnad', 'Shipping', 'Hardware', 'Installasjon',
    'Oppsett', 'Setup', 'Arbeidstimer', 'Feste Rekkverk', 'Feste dekk',
    'Fangstr ERS'
}


async def import_new_csv():
    """Import invoices and credit notes from NEW CSV files"""

    print("="*80)
    print("CSV INVOICE IMPORT - NEW FILES (2024-2025)")
    print("="*80)

    # NEW Invoice CSV files
    invoice_files = [
        "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (5)1jan2024-30jun.csv",
        "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (5)1jul2024-31dec2024.csv",
        "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (5)1jan2025-30jun.csv",
        "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (5)1jul2025-12oct.csv",
    ]

    # Credit Note CSV
    creditnote_file = "c:/Users/nikolai/Code/Saas_analyse/excel/Credit_Note.csv"

    # Step 1: Load all invoice data
    print("\n[1] LOADING INVOICE DATA")
    print("-"*80)
    all_invoices = []
    for file in invoice_files:
        df = pd.read_csv(file)
        df['transaction_type'] = 'invoice'
        all_invoices.append(df)
        print(f"  [OK] Loaded {file.split('/')[-1]}: {len(df)} lines")

    # Step 2: Load credit notes
    print("\n[2] LOADING CREDIT NOTES")
    print("-"*80)
    cn_df = pd.read_csv(creditnote_file)

    # Map credit note columns to invoice format
    cn_df = cn_df.rename(columns={
        'CreditNotes ID': 'Invoice ID',
        'Credit Note Number': 'Invoice Number',
        'Credit Note Date': 'Invoice Date',
        'Credit Note Status': 'Invoice Status'
    })
    cn_df['transaction_type'] = 'creditnote'
    cn_df['Due Date'] = cn_df['Invoice Date']  # Credit notes don't have due dates
    all_invoices.append(cn_df)
    print(f"  [OK] Loaded {len(cn_df)} credit note lines")

    # Step 3: Combine all data
    print("\n[3] COMBINING DATA")
    print("-"*80)
    combined_df = pd.concat(all_invoices, ignore_index=True)
    print(f"  [OK] Total lines: {len(combined_df)}")

    # Step 4: Filter out hardware and one-time products
    print("\n[4] FILTERING")
    print("-"*80)
    before_count = len(combined_df)

    # Filter by Item Name (specific hardware products)
    combined_df = combined_df[~combined_df['Item Name'].isin(HARDWARE_CODES)]

    after_count = len(combined_df)
    filtered_count = before_count - after_count
    print(f"  [OK] Filtered out {filtered_count} hardware/one-time lines")
    print(f"  [OK] Remaining: {after_count} recurring subscription lines")

    # Step 5: Import to database
    print("\n[5] IMPORTING TO DATABASE")
    print("-"*80)

    async with AsyncSessionLocal() as session:
        invoice_service = InvoiceService(session)

        # Clear existing
        print("  Clearing existing invoices...")
        await session.execute(delete(InvoiceLineItem))
        await session.execute(delete(Invoice))
        await session.commit()
        print("  [OK] Cleared")

        # Parse dates
        combined_df['Invoice Date'] = pd.to_datetime(combined_df['Invoice Date'], errors='coerce')
        combined_df['Due Date'] = pd.to_datetime(combined_df['Due Date'], errors='coerce')

        # Group by Invoice ID
        grouped = combined_df.groupby(['Invoice ID', 'transaction_type'])
        total = len(grouped)

        print(f"  Processing {total} invoices/credit notes...")

        imported_count = 0
        skipped_count = 0
        error_count = 0
        total_line_items = 0

        for (invoice_id, trans_type), lines in grouped:
            try:
                first = lines.iloc[0]

                def parse_date(date_val):
                    if pd.isna(date_val):
                        return None
                    if isinstance(date_val, datetime):
                        return date_val.replace(tzinfo=None)
                    return pd.to_datetime(date_val).replace(tzinfo=None)

                invoice_date = parse_date(first['Invoice Date'])
                due_date = parse_date(first['Due Date'])

                if not invoice_date:
                    skipped_count += 1
                    continue

                # Create Invoice/CreditNote
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
                    tax_total=0.0,
                    total=float(first.get('Total', 0)),
                    balance=float(first.get('Balance', 0)),
                    status=str(first.get('Invoice Status', 'sent')).lower(),
                    transaction_type=trans_type,
                    created_time=invoice_date,
                    updated_time=invoice_date,
                )
                session.add(invoice)

                # Process line items
                for _, item_row in lines.iterrows():
                    item_name = str(item_row.get('Item Name', '')) if pd.notna(item_row.get('Item Name')) else ''
                    item_desc = str(item_row.get('Item Desc', '')) if pd.notna(item_row.get('Item Desc')) else ''

                    price = float(item_row.get('Item Price', 0))
                    quantity = int(item_row.get('Quantity', 1))
                    item_total = float(item_row.get('Item Total', price * quantity))

                    # For credit notes, make amounts negative
                    if trans_type == 'creditnote':
                        price = -abs(price)
                        item_total = -abs(item_total)

                    # Calculate MRR
                    mrr_calc = invoice_service.calculate_mrr_from_line_item({
                        'description': item_desc,
                        'name': item_name,
                        'price': abs(price),  # Use absolute for calculation
                        'invoice_date': invoice_date
                    })

                    # Apply sign to MRR
                    mrr_per_month = mrr_calc['mrr_per_month']
                    if trans_type == 'creditnote':
                        mrr_per_month = -abs(mrr_per_month)

                    line_item = InvoiceLineItem(
                        invoice_id=str(invoice_id),
                        item_id='',
                        product_id=str(item_row.get('Product ID', '')) if pd.notna(item_row.get('Product ID')) else '',
                        subscription_id=str(item_row.get('subscription_id', '')) if pd.notna(item_row.get('subscription_id')) else '',
                        name=item_name,
                        description=item_desc,
                        code='',
                        unit='',
                        price=price,
                        quantity=quantity,
                        item_total=item_total,
                        tax_percentage=float(item_row.get('Item Tax %', 0)) if pd.notna(item_row.get('Item Tax %')) else 0.0,
                        tax_name=str(item_row.get('Item Tax', '')) if pd.notna(item_row.get('Item Tax')) else '',
                        period_start_date=mrr_calc['period_start_date'],
                        period_end_date=mrr_calc['period_end_date'],
                        period_months=mrr_calc['period_months'],
                        mrr_per_month=mrr_per_month,
                    )
                    session.add(line_item)
                    total_line_items += 1

                imported_count += 1

                if imported_count % 100 == 0:
                    await session.commit()
                    print(f"    Progress: {imported_count}/{total} ({(imported_count/total)*100:.1f}%), Line items: {total_line_items}")

            except Exception as e:
                print(f"    [ERROR] {invoice_id}: {e}")
                error_count += 1
                continue

        await session.commit()
        print(f"\n  [OK] Import complete")
        print(f"    Imported: {imported_count} transactions")
        print(f"    Skipped: {skipped_count}")
        print(f"    Errors: {error_count}")
        print(f"    Total line items: {total_line_items}")

        # Step 6: Generate snapshots
        print("\n[6] GENERATING MONTHLY MRR SNAPSHOTS")
        print("-"*80)
        from dateutil.relativedelta import relativedelta

        today = datetime.utcnow()
        snapshots_created = []

        for i in range(24):  # Last 24 months
            month_date = today - relativedelta(months=i)
            month_str = month_date.strftime("%Y-%m")

            try:
                snapshot = await invoice_service.generate_monthly_snapshot(month_str)
                if snapshot.mrr > 0:
                    snapshots_created.append(month_str)
                    print(f"  [OK] {month_str}: MRR = {snapshot.mrr:,.2f} NOK, Customers = {snapshot.total_customers}")
            except Exception as e:
                pass

        print()
        print("="*80)
        print("IMPORT COMPLETE")
        print("="*80)
        print(f"Transactions imported: {imported_count}")
        print(f"Line items imported: {total_line_items}")
        print(f"Snapshots generated: {len(snapshots_created)}")


if __name__ == "__main__":
    asyncio.run(import_new_csv())
