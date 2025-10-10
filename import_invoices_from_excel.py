"""
Import invoices from Excel (Receivable Details) to database

This script:
1. Reads product categorization from Parameters sheet
2. Filters out one-time sales (Periodisering = 1 or 3)
3. Parses billing periods from description field
4. Calculates MRR for recurring subscriptions
5. Imports to database
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from services.invoice import InvoiceService
from sqlalchemy import delete


async def import_invoices_from_excel():
    """Import invoices from Receivable Details Excel file"""

    print("=== INVOICE IMPORT FROM EXCEL ===\n")

    # File paths
    receivable_file = "C:/Users/nikolai/Code/Saas_analyse/excel/Receivable Details.xlsx"
    parameters_file = "c:/Users/nikolai/Downloads/Zoho master sales report pr 30.09.2025.xlsx"

    # Step 1: Read Parameters to identify subscription products
    print("Step 1: Loading product categorization from Parameters...")
    params_df = pd.read_excel(parameters_file, sheet_name='Parameters')

    # Create mapping: Item name -> Periodisering
    item_periodization = {}
    for _, row in params_df.iterrows():
        item_name = row['Item name']
        periodisering = row['Periodisering']
        if pd.notna(item_name):
            item_periodization[item_name] = periodisering

    print(f"  [OK] Loaded {len(item_periodization)} products")
    print(f"  - One-time (Periodisering = 1): {sum(1 for v in item_periodization.values() if v == 1)}")
    print(f"  - One-time (Periodisering = 3): {sum(1 for v in item_periodization.values() if v == 3)}")
    print(f"  - Recurring (Periodisering = 12): {sum(1 for v in item_periodization.values() if v == 12)}")
    print()

    # Step 2: Read Receivable Details
    print("Step 2: Loading invoice data from Receivable Details...")
    df = pd.read_excel(receivable_file, skiprows=0)

    # Fix headers (first row contains actual headers)
    headers = df.iloc[0].tolist()
    df.columns = headers
    df = df[1:].reset_index(drop=True)

    # Fix duplicate column names (bcy_total, fcy_total appear twice)
    # Use suffix to make them unique
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        cols[cols[cols == dup].index.values.tolist()] = [dup if i == 0 else f'{dup}_{i}' for i in range(sum(cols == dup))]
    df.columns = cols

    print(f"  [OK] Loaded {len(df)} invoice line items")
    print()

    # Step 3: Filter and categorize
    print("Step 3: Filtering and categorizing line items...")

    # Add periodization column based on product_name or item_name
    df['periodization'] = df['product_name'].apply(lambda x: item_periodization.get(x, None))

    # If product_name didn't match, try description
    df['periodization'] = df.apply(
        lambda row: item_periodization.get(row['description'], row['periodization'])
        if pd.isna(row['periodization']) else row['periodization'],
        axis=1
    )

    # Filter: Only invoices (not creditnotes)
    invoices_df = df[df['transaction_type'] == 'invoice'].copy()

    # Categorize
    one_time_df = invoices_df[invoices_df['periodization'].isin([1, 3])]
    recurring_df = invoices_df[invoices_df['periodization'] == 12]
    unknown_df = invoices_df[invoices_df['periodization'].isna()]

    print(f"  Total invoice lines: {len(invoices_df)}")
    print(f"  - One-time (excluded from MRR): {len(one_time_df)}")
    print(f"  - Recurring (included in MRR): {len(recurring_df)}")
    print(f"  - Unknown periodization: {len(unknown_df)}")
    print()

    if len(unknown_df) > 0:
        print("  [WARNING] Unknown products (will use description parsing):")
        print(unknown_df['product_name'].value_counts().head(10))
        print()

    # Step 4: Import to database
    print("Step 4: Importing to database...")

    async with AsyncSessionLocal() as session:
        invoice_service = InvoiceService(session)

        # Clear existing invoices (optional - comment out to keep existing data)
        print("  Clearing existing invoices...")
        await session.execute(delete(InvoiceLineItem))
        await session.execute(delete(Invoice))
        await session.commit()
        print("  [OK] Cleared existing data")
        print()

        # Group by transaction_id (invoice)
        grouped = df[df['transaction_type'] == 'invoice'].groupby('transaction_id')
        total_invoices = len(grouped)

        print(f"  Processing {total_invoices} invoices...")

        imported_count = 0
        skipped_count = 0

        for transaction_id, line_items in grouped:
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

                invoice_date = parse_date(first_item['transaction_date'])
                due_date = parse_date(first_item.get('due_date'))

                # Create Invoice
                invoice = Invoice(
                    id=str(transaction_id),
                    invoice_number=str(first_item['transaction_number']),
                    invoice_date=invoice_date,
                    due_date=due_date,
                    customer_id=str(first_item['customer_id']),
                    customer_name=str(first_item['customer_name']),
                    customer_email="",  # Not in Excel
                    currency_code=str(first_item.get('currency_code', 'NOK')),
                    sub_total=float(first_item.get('bcy_total', 0)),
                    tax_total=float(first_item.get('bcy_tax_amount', 0)),
                    total=float(first_item.get('fcy_total_with_tax', 0)),
                    balance=0.0,  # Not in Excel
                    status=str(first_item.get('status', 'sent')),
                    transaction_type='invoice',
                    created_time=invoice_date,
                    updated_time=invoice_date,
                )
                session.add(invoice)

                # Process line items
                for _, item_row in line_items.iterrows():
                    # Get periodization for this product
                    product_name = item_row.get('product_name')
                    description = item_row.get('description', '')
                    periodization = item_periodization.get(product_name, None)

                    # Skip one-time products (Periodisering = 1 or 3)
                    if periodization in [1, 3]:
                        continue

                    # Parse price
                    price = float(item_row.get('bcy_item_price', 0))
                    quantity = int(item_row.get('quantity_ordered', 1))
                    item_total = float(item_row.get('bcy_total', price * quantity))

                    # Calculate MRR from description
                    mrr_calc = invoice_service.calculate_mrr_from_line_item({
                        'description': description,
                        'price': price
                    })

                    # If description parsing failed and we know it's annual (Periodisering = 12)
                    if mrr_calc['period_months'] == 1 and periodization == 12:
                        # Override: This is an annual subscription
                        mrr_calc['period_months'] = 12
                        mrr_calc['mrr_per_month'] = price / 12

                    # Create line item
                    line_item = InvoiceLineItem(
                        invoice_id=str(transaction_id),
                        item_id=str(item_row.get('item_id', '')),
                        product_id=str(item_row.get('product_id', '')),
                        subscription_id='',  # Not in Excel
                        name=str(product_name) if pd.notna(product_name) else str(description),
                        description=str(description),
                        code='',  # Not in Excel
                        unit='',  # Not in Excel
                        price=price,
                        quantity=quantity,
                        item_total=item_total,
                        tax_percentage=float(item_row.get('tax_percentage', 0)),
                        tax_name=str(item_row.get('tax_name', '')),
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
                print(f"    [ERROR] Error importing invoice {transaction_id}: {e}")
                skipped_count += 1
                continue

        # Final commit
        await session.commit()
        print(f"  [OK] Imported {imported_count} invoices")
        print(f"  [SKIPPED] {skipped_count} invoices due to errors")
        print()

        # Step 5: Generate monthly snapshots
        print("Step 5: Generating monthly MRR snapshots...")

        today = datetime.utcnow()
        from dateutil.relativedelta import relativedelta

        snapshots_created = []
        for i in range(12):
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
    asyncio.run(import_invoices_from_excel())
