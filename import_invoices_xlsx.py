"""
Import invoice data from Zoho Excel exports (FULL HISTORY)
Uses parameters.xlsx mapping for periodization and hardware filtering
Supports .xlsx and .xls file formats
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from sqlalchemy import delete


async def import_from_excel():
    """Import invoices from Zoho Excel exports using parameters mapping"""

    print("="*80)
    print("ZOHO EXCEL INVOICE IMPORT - FULL HISTORY (WITH PARAMETERS MAPPING)")
    print("="*80)

    # Load parameters mapping
    print("\n[1] LOADING PARAMETERS MAPPING")
    print("-"*80)
    params_df = pd.read_excel("c:/Users/nikolai/Downloads/parameters.xlsx")

    # Create lookup dictionaries
    # Key: Item name -> Value: Periodization months
    # ONLY include Fangstdagbok, Support, and VMS
    periodization_map = {}
    allowed_groups = ['Fangstdagbok', 'Support', 'VMS']

    group_counts = {group: 0 for group in allowed_groups}

    for _, row in params_df.iterrows():
        item_name = str(row.get('Item name', '')).strip() if pd.notna(row.get('Item name')) else ''
        if not item_name:
            continue

        # Check if this item belongs to an allowed revenue group
        inntektsgruppe = str(row.get('Inntektsgruppe', '')).strip() if pd.notna(row.get('Inntektsgruppe')) else ''

        if inntektsgruppe not in allowed_groups:
            continue  # Skip items not in allowed groups

        # Get periodization value (default to 12 if not specified)
        periodisering = int(row.get('Periodisering', 12)) if pd.notna(row.get('Periodisering')) else 12
        periodization_map[item_name] = periodisering
        group_counts[inntektsgruppe] += 1

    print(f"  [OK] Loaded {len(periodization_map)} item mappings from allowed groups:")
    for group in allowed_groups:
        print(f"      - {group}: {group_counts[group]} items")
    print(f"  [OK] All other revenue groups will be excluded")

    # Step 2: Load Excel data from Zoho exports (invoices + credit notes)
    print("\n[2] LOADING ZOHO EXCEL FILES")
    print("-"*80)
    all_data = []

    # Load invoice file (complete Zoho export - ALL invoice data with line items)
    invoice_file = r"c:\Users\nikolai\Downloads\Dualog Fisknett AS_2025-10-13\Invoice.xls"
    print(f"  Loading {invoice_file}...")
    inv_df = pd.read_excel(invoice_file)
    inv_df['transaction_type'] = 'invoice'
    inv_df = inv_df.reset_index(drop=True)  # Reset index to avoid conflicts
    print(f"  [OK] Loaded invoice file: {len(inv_df)} lines")

    # Load credit note file (merged file with ALL fields including line items)
    cn_file = r"c:\Users\nikolai\AppData\Roaming\Microsoft\Windows\Network Shortcuts\Credit_Note merged.xlsx"
    print(f"  Loading {cn_file}...")
    cn_df = pd.read_excel(cn_file)
    cn_df = cn_df.reset_index(drop=True)  # Reset index to avoid conflicts

    # Standardize column names (fix spacing differences)
    cn_df = cn_df.rename(columns={
        'Billing Street 2': 'Billing Street2',
        'Shipping Street 2': 'Shipping Street2'
    })

    # Rename "Invoice Number" (applied invoice) to "Applied Invoice Number" to avoid conflicts
    cn_df = cn_df.rename(columns={
        'Invoice Number': 'Applied Invoice Number'
    })

    # Map credit note columns to invoice format
    cn_df = cn_df.rename(columns={
        'CreditNotes ID': 'Invoice ID',
        'Credit Note Number': 'Invoice Number',
        'Credit Note Date': 'Invoice Date',
        'Credit Note Status': 'Invoice Status',
        'CF.RKAL': 'CF.Radiokallesignal'  # Standardize call sign column name
    })
    cn_df['transaction_type'] = 'creditnote'
    cn_df['Due Date'] = cn_df['Invoice Date']  # Credit notes don't have due dates
    print(f"  [OK] Loaded credit note file: {len(cn_df)} lines")

    # Combine all data - stack dataframes
    print(f"  Combining invoices and credit notes...")
    combined_df = pd.concat([inv_df, cn_df], ignore_index=True, sort=False)
    print(f"\n[3] DATA LOADED")
    print("-"*80)
    print(f"  [OK] Total lines: {len(combined_df)} (invoices + credit notes)")

    # Step 4: Filter to only allowed revenue groups (Fangstdagbok, Support, VMS)
    print("\n[4] FILTERING TO ALLOWED REVENUE GROUPS")
    print("-"*80)
    before_count = len(combined_df)

    # Only keep items that are in periodization_map (i.e., Fangstdagbok, Support, VMS)
    def is_allowed_revenue_group(row):
        item_name = str(row.get('Item Name', '')).strip() if pd.notna(row.get('Item Name')) else ''
        return item_name in periodization_map

    combined_df = combined_df[combined_df.apply(is_allowed_revenue_group, axis=1)]

    after_count = len(combined_df)
    filtered_count = before_count - after_count
    print(f"  [OK] Filtered out {filtered_count} items from other revenue groups")
    print(f"  [OK] Remaining: {after_count} items from Fangstdagbok, Support, VMS")

    # Calculate Start Date and End Date
    print(f"\n  Calculating period dates...")
    combined_df['Start Date'] = pd.NaT
    combined_df['End Date'] = pd.NaT

    # First pass: Calculate periods for INVOICES
    print(f"  Step 1: Calculating invoice periods...")
    for idx, row in combined_df.iterrows():
        if row['transaction_type'] != 'invoice':
            continue  # Skip credit notes in first pass

        item_name = str(row.get('Item Name', '')).strip() if pd.notna(row.get('Item Name')) else ''
        invoice_date = row['Invoice Date']

        if item_name in periodization_map:
            period_months = periodization_map[item_name]
            # Start from invoice date, extend forward by period_months
            start_date = pd.to_datetime(invoice_date)
            # Calculate end date by adding months
            end_date = start_date + pd.DateOffset(months=period_months) - pd.DateOffset(days=1)
            combined_df.at[idx, 'Start Date'] = start_date
            combined_df.at[idx, 'End Date'] = end_date

    # Second pass: Calculate periods for CREDIT NOTES (match to invoice end date)
    print(f"  Step 2: Matching credit note periods to invoice end dates...")

    # Create invoice lookup: Invoice Number -> End Date
    invoice_periods = {}
    for idx, row in combined_df.iterrows():
        if row['transaction_type'] == 'invoice' and pd.notna(row.get('End Date')):
            inv_number = str(row['Invoice Number']).strip()
            end_date = row['End Date']
            # Store the LATEST end date if multiple lines for same invoice
            if inv_number not in invoice_periods or end_date > invoice_periods[inv_number]:
                invoice_periods[inv_number] = end_date

    matched_cn = 0
    unmatched_cn = 0

    for idx, row in combined_df.iterrows():
        if row['transaction_type'] != 'creditnote':
            continue  # Skip invoices

        cn_date = pd.to_datetime(row['Invoice Date'])
        applied_invoice_num = str(row.get('Applied Invoice Number', '')).strip()

        # Try to match with original invoice
        if applied_invoice_num and applied_invoice_num in invoice_periods:
            # MATCH FOUND: Use invoice's end date
            invoice_end_date = invoice_periods[applied_invoice_num]
            combined_df.at[idx, 'Start Date'] = cn_date
            combined_df.at[idx, 'End Date'] = invoice_end_date
            matched_cn += 1
        else:
            # NO MATCH: Fallback to standard periodization
            item_name = str(row.get('Item Name', '')).strip() if pd.notna(row.get('Item Name')) else ''
            if item_name in periodization_map:
                period_months = periodization_map[item_name]
                end_date = cn_date + pd.DateOffset(months=period_months) - pd.DateOffset(days=1)
                combined_df.at[idx, 'Start Date'] = cn_date
                combined_df.at[idx, 'End Date'] = end_date
            unmatched_cn += 1

    print(f"  [OK] Period dates calculated")
    print(f"      Credit notes matched to invoice: {matched_cn}")
    print(f"      Credit notes using fallback: {unmatched_cn}")

    # Step 5: Ensure tables exist
    print("\n[5] ENSURING DATABASE TABLES EXIST")
    print("-"*80)
    from database import engine
    from models.invoice import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  [OK] All tables created (if missing)")

    # Step 6: Import to database
    print("\n[6] IMPORTING TO DATABASE")
    print("-"*80)

    async with AsyncSessionLocal() as session:
        # Clear existing
        print("  Clearing existing invoices...")
        await session.execute(delete(InvoiceLineItem))
        await session.execute(delete(Invoice))
        await session.commit()
        print("  [OK] Cleared")

        # Parse dates
        combined_df['Invoice Date'] = pd.to_datetime(combined_df['Invoice Date'], errors='coerce')
        combined_df['Due Date'] = pd.to_datetime(combined_df['Due Date'], errors='coerce')
        combined_df['Start Date'] = pd.to_datetime(combined_df['Start Date'], errors='coerce')
        combined_df['End Date'] = pd.to_datetime(combined_df['End Date'], errors='coerce')

        # Group by Invoice ID and transaction_type
        grouped = combined_df.groupby(['Invoice ID', 'transaction_type'])
        total = len(grouped)

        print(f"  Processing {total} transactions (invoices + credit notes)...")

        imported_count = 0
        skipped_count = 0
        error_count = 0
        total_line_items = 0
        invoice_count = 0
        creditnote_count = 0

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

                # Get invoice status
                invoice_status = str(first.get('Invoice Status', '')).lower()

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
                    status=invoice_status if invoice_status else 'sent',
                    transaction_type=trans_type,
                    created_time=invoice_date,
                    updated_time=invoice_date,
                )
                session.add(invoice)

                if trans_type == 'invoice':
                    invoice_count += 1
                else:
                    creditnote_count += 1

                # Process line items
                for _, item_row in lines.iterrows():
                    item_name = str(item_row.get('Item Name', '')) if pd.notna(item_row.get('Item Name')) else ''
                    item_desc = str(item_row.get('Item Desc', '')) if pd.notna(item_row.get('Item Desc')) else ''
                    item_code = str(item_row.get('Item Code', '')) if pd.notna(item_row.get('Item Code')) else ''

                    # Get quantity and item total
                    quantity = int(item_row.get('Quantity', 1))
                    item_price = float(item_row.get('Item Price', 0))
                    item_total = float(item_row.get('Item Total', item_price * quantity))

                    # For credit notes, make amounts negative
                    if trans_type == 'creditnote':
                        item_price = -abs(item_price)
                        item_total = -abs(item_total)

                    # Get period dates from Start Date and End Date columns
                    period_start_date = parse_date(item_row.get('Start Date'))
                    period_end_date = parse_date(item_row.get('End Date'))

                    # Get period_months from parameters mapping
                    # This is the AUTHORITATIVE source for periodization
                    period_months = periodization_map.get(item_name, 12)  # Default to 12 if not found

                    # Calculate MRR using the correct periodization
                    mrr_per_month = item_total / period_months

                    # Get subscription ID
                    subscription_id = str(item_row.get('Subscription ID', '')) if pd.notna(item_row.get('Subscription ID')) else ''

                    # Get vessel information
                    vessel_name = str(item_row.get('CF.Fartøy', '')) if pd.notna(item_row.get('CF.Fartøy')) else ''
                    call_sign = str(item_row.get('CF.Radiokallesignal', '')) if pd.notna(item_row.get('CF.Radiokallesignal')) else ''

                    line_item = InvoiceLineItem(
                        invoice_id=str(invoice_id),
                        item_id=str(item_row.get('Item ID', '')) if pd.notna(item_row.get('Item ID')) else '',
                        product_id='',
                        subscription_id=subscription_id,
                        name=item_name,
                        description=item_desc,
                        code=item_code,
                        unit='',
                        vessel_name=vessel_name,
                        call_sign=call_sign,
                        price=item_price,
                        quantity=quantity,
                        item_total=item_total,
                        tax_percentage=float(item_row.get('Item Tax %', 0)) if pd.notna(item_row.get('Item Tax %')) else 0.0,
                        tax_name=str(item_row.get('Item Tax', '')) if pd.notna(item_row.get('Item Tax')) else '',
                        period_start_date=period_start_date,
                        period_end_date=period_end_date,
                        period_months=period_months,
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
        print(f"    Imported: {imported_count} transactions ({invoice_count} invoices, {creditnote_count} credit notes)")
        print(f"    Skipped: {skipped_count}")
        print(f"    Errors: {error_count}")
        print(f"    Total line items: {total_line_items}")

        # Step 7: Generate snapshots
        print("\n[7] GENERATING MONTHLY MRR SNAPSHOTS")
        print("-"*80)
        from services.invoice import InvoiceService
        from dateutil.relativedelta import relativedelta

        invoice_service = InvoiceService(session)
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

        # Step 8: Create InvoiceSyncStatus to mark import complete
        print("\n[8] CREATING SYNC STATUS")
        print("-"*80)
        from models.invoice import InvoiceSyncStatus
        from sqlalchemy import delete as sql_delete

        # Clear any existing sync status records
        await session.execute(sql_delete(InvoiceSyncStatus))

        # Create sync status record with cutoff date from Excel export
        # This tells API sync: "Everything before 2025-10-13 is imported, only fetch newer"
        cutoff_date = datetime(2025, 10, 13, 23, 59, 59)  # End of Oct 13

        sync_status = InvoiceSyncStatus(
            last_sync_time=cutoff_date,
            invoices_synced=invoice_count,
            creditnotes_synced=creditnote_count,
            success=True,
            error_message=None
        )
        session.add(sync_status)
        await session.commit()

        print(f"  [OK] Created sync status with cutoff: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  [OK] Future API syncs will only fetch records modified after {cutoff_date.strftime('%Y-%m-%d')}")

        print()
        print("="*80)
        print("IMPORT COMPLETE")
        print("="*80)
        print(f"Invoices imported: {invoice_count}")
        print(f"Credit notes imported: {creditnote_count}")
        print(f"Total line items: {total_line_items}")
        print(f"Snapshots generated: {len(snapshots_created)}")
        print(f"Sync cutoff date: {cutoff_date.strftime('%Y-%m-%d')}")
        print(f"\nNEXT STEP: Run API sync to fetch any new invoices/credit notes after {cutoff_date.strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    asyncio.run(import_from_excel())
