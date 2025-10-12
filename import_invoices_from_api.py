"""
Import invoices directly from Zoho Billing API with parameters.xlsx mapping
Uses same strategy as CSV import for accurate periodization
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from services.invoice import InvoiceService
from services.zoho import ZohoClient
from sqlalchemy import delete
from config import settings


async def fetch_invoices_from_zoho(zoho_client: ZohoClient, invoice_type: str = "invoice", page: int = 1, per_page: int = 200, max_retries: int = 2):
    """
    Fetch invoices or credit notes from Zoho API with retry on 401

    Args:
        zoho_client: Initialized Zoho client
        invoice_type: "invoice" or "creditnote"
        page: Page number
        per_page: Results per page (max 200)
        max_retries: Maximum number of retry attempts

    Returns:
        List of invoice/creditnote data
    """
    endpoint = "invoices" if invoice_type == "invoice" else "creditnotes"
    url = f"{zoho_client.base_url}/billing/v1/{endpoint}"

    params = {
        "page": page,
        "per_page": per_page,
    }

    import httpx

    for attempt in range(max_retries):
        headers = await zoho_client._get_headers()

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                return data.get(endpoint, [])
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401 and attempt < max_retries - 1:
                    print(f"401 error fetching {endpoint} page {page}, refreshing token and retrying...")
                    zoho_client.access_token = None  # Force token refresh
                    await asyncio.sleep(1)
                    continue
                else:
                    print(f"Error fetching {endpoint} page {page}: {e}")
                    return []
            except Exception as e:
                print(f"Error fetching {endpoint} page {page}: {e}")
                return []

    return []


async def fetch_all_invoices(zoho_client: ZohoClient, invoice_type: str = "invoice"):
    """Fetch ALL invoices/creditnotes across all pages"""
    all_records = []
    page = 1
    per_page = 200

    print(f"Fetching {invoice_type}s from Zoho API...")

    while True:
        records = await fetch_invoices_from_zoho(zoho_client, invoice_type, page, per_page)

        if not records:
            break

        all_records.extend(records)
        print(f"  Page {page}: {len(records)} {invoice_type}s (total so far: {len(all_records)})")

        if len(records) < per_page:
            break

        page += 1

    print(f"Total {invoice_type}s fetched: {len(all_records)}")
    return all_records


async def fetch_invoice_details(zoho_client: ZohoClient, invoice_id: str, invoice_type: str = "invoice", max_retries: int = 2):
    """Fetch detailed invoice data including line items with retry on 401"""
    endpoint = "invoices" if invoice_type == "invoice" else "creditnotes"
    url = f"{zoho_client.base_url}/billing/v1/{endpoint}/{invoice_id}"

    import httpx

    for attempt in range(max_retries):
        headers = await zoho_client._get_headers()

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                # Return the invoice/creditnote object
                return data.get(endpoint[:-1])  # "invoice" or "creditnote" (singular)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401 and attempt < max_retries - 1:
                    # Token expired, force refresh and retry
                    print(f"401 error for {endpoint} {invoice_id}, refreshing token and retrying...")
                    zoho_client.access_token = None  # Force token refresh
                    await asyncio.sleep(1)  # Brief delay before retry
                    continue
                else:
                    print(f"Error fetching {endpoint} {invoice_id}: {e}")
                    return None
            except Exception as e:
                print(f"Error fetching {endpoint} {invoice_id}: {e}")
                return None

    return None


async def import_from_api():
    """Import all invoices and credit notes from Zoho API using parameters mapping"""

    print("="*80)
    print("ZOHO API INVOICE IMPORT - WITH PARAMETERS MAPPING")
    print("="*80)

    # Step 1: Load parameters mapping (same as CSV import)
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

    # Step 2: Initialize Zoho client
    zoho_client = ZohoClient(
        client_id=settings.zoho_client_id,
        client_secret=settings.zoho_client_secret,
        refresh_token=settings.zoho_refresh_token,
        org_id=settings.zoho_org_id,
        base_url=settings.zoho_base,
    )

    # Step 3: Fetch all invoice and credit note IDs (summaries only)
    print("\n[2] FETCHING INVOICE AND CREDIT NOTE IDs")
    print("-"*80)
    invoice_list = await fetch_all_invoices(zoho_client, "invoice")
    creditnote_list = await fetch_all_invoices(zoho_client, "creditnote")

    total_to_fetch = len(invoice_list) + len(creditnote_list)
    print(f"\n  Total to import: {len(invoice_list)} invoices + {len(creditnote_list)} credit notes = {total_to_fetch} transactions")

    # Step 4: Clear existing data
    print("\n[3] CLEARING EXISTING DATABASE")
    print("-"*80)
    async with AsyncSessionLocal() as session:
        await session.execute(delete(InvoiceLineItem))
        await session.execute(delete(Invoice))
        await session.commit()
        print("  [OK] Cleared existing invoices and line items")

    # Step 5: Fetch detailed data and import
    print("\n[4] FETCHING DETAILED DATA AND IMPORTING")
    print("-"*80)

    async with AsyncSessionLocal() as session:
        imported_count = 0
        skipped_count = 0
        error_count = 0
        total_line_items = 0
        filtered_hardware_count = 0

        # Process invoices
        for idx, inv_summary in enumerate(invoice_list, 1):
            try:
                invoice_id = inv_summary.get('invoice_id')

                # Fetch full invoice details
                invoice_data = await fetch_invoice_details(zoho_client, invoice_id, "invoice")

                if not invoice_data:
                    skipped_count += 1
                    continue

                # Parse dates
                invoice_date_str = invoice_data.get('date')
                due_date_str = invoice_data.get('due_date')

                invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d") if invoice_date_str else None
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d") if due_date_str else None

                if not invoice_date:
                    skipped_count += 1
                    continue

                # Create Invoice
                invoice = Invoice(
                    id=invoice_id,
                    invoice_number=invoice_data.get('invoice_number', ''),
                    invoice_date=invoice_date,
                    due_date=due_date,
                    customer_id=str(invoice_data.get('customer_id', '')),
                    customer_name=invoice_data.get('customer_name', ''),
                    customer_email=invoice_data.get('email', ''),
                    currency_code=invoice_data.get('currency_code', 'NOK'),
                    sub_total=float(invoice_data.get('sub_total', 0)),
                    tax_total=float(invoice_data.get('tax_total', 0)),
                    total=float(invoice_data.get('total', 0)),
                    balance=float(invoice_data.get('balance', 0)),
                    status=invoice_data.get('status', 'sent').lower(),
                    transaction_type='invoice',
                    created_time=invoice_date,
                    updated_time=invoice_date,
                )
                session.add(invoice)

                # Process line items (Zoho uses 'invoice_items' not 'line_items')
                line_items = invoice_data.get('invoice_items', [])
                invoice_has_valid_items = False

                for item in line_items:
                    item_name = item.get('name', '') or item.get('item_name', '')
                    item_code = item.get('code', '') or item.get('item_code', '')
                    item_desc = item.get('description', '')

                    # Filter using parameters mapping (same as CSV import)
                    if item_name not in periodization_map:
                        filtered_hardware_count += 1
                        continue  # Skip items not in allowed revenue groups

                    price = float(item.get('price', 0))
                    quantity = int(item.get('quantity', 1))
                    item_total = float(item.get('item_total', price * quantity))

                    # Get periodization from parameters mapping (AUTHORITATIVE)
                    period_months = periodization_map[item_name]

                    # Calculate MRR using the correct periodization
                    mrr_per_month = item_total / period_months

                    # Get period dates from item (if available)
                    # Zoho API may include subscription_start_date and subscription_end_date
                    period_start_date = None
                    period_end_date = None

                    # Try to get from subscription dates in item
                    if item.get('subscription_start_date'):
                        period_start_date = datetime.strptime(item['subscription_start_date'], "%Y-%m-%d")
                    if item.get('subscription_end_date'):
                        period_end_date = datetime.strptime(item['subscription_end_date'], "%Y-%m-%d")

                    # If not available, calculate from invoice date + period_months
                    if not period_start_date:
                        period_start_date = invoice_date
                    if not period_end_date:
                        period_end_date = period_start_date + pd.DateOffset(months=period_months) - pd.DateOffset(days=1)

                    # Get vessel information from custom fields
                    vessel_name = ''
                    call_sign = ''
                    custom_fields = item.get('custom_fields', [])
                    for cf in custom_fields:
                        if cf.get('label') == 'Fartøy':
                            vessel_name = str(cf.get('value', ''))
                        elif cf.get('label') == 'Radiokallesignal':
                            call_sign = str(cf.get('value', ''))

                    line_item = InvoiceLineItem(
                        invoice_id=invoice_id,
                        item_id=str(item.get('item_id', '')),
                        product_id=str(item.get('product_id', '')),
                        subscription_id=str(item.get('subscription_id', '')),
                        name=item_name,
                        description=item_desc,
                        code=item_code,
                        unit=item.get('unit', ''),
                        vessel_name=vessel_name,
                        call_sign=call_sign,
                        price=price,
                        quantity=quantity,
                        item_total=item_total,
                        tax_percentage=float(item.get('tax_percentage', 0)),
                        tax_name=item.get('tax_name', ''),
                        period_start_date=period_start_date,
                        period_end_date=period_end_date,
                        period_months=period_months,
                        mrr_per_month=mrr_per_month,
                    )
                    session.add(line_item)
                    total_line_items += 1
                    invoice_has_valid_items = True

                if invoice_has_valid_items:
                    imported_count += 1

                # Commit every 100 transactions
                if imported_count % 100 == 0:
                    await session.commit()
                    print(f"    Invoices: {imported_count}/{len(invoice_list)} ({(imported_count/len(invoice_list)*100):.1f}%), Line items: {total_line_items}")

            except Exception as e:
                print(f"    [ERROR] Invoice {idx}: {e}")
                error_count += 1
                continue

        # Process credit notes
        for idx, cn_summary in enumerate(creditnote_list, 1):
            try:
                creditnote_id = cn_summary.get('creditnote_id')

                # Fetch full creditnote details
                cn_data = await fetch_invoice_details(zoho_client, creditnote_id, "creditnote")

                if not cn_data:
                    skipped_count += 1
                    continue

                # Parse dates
                cn_date_str = cn_data.get('date')
                cn_date = datetime.strptime(cn_date_str, "%Y-%m-%d") if cn_date_str else None

                if not cn_date:
                    skipped_count += 1
                    continue

                # Create Credit Note as Invoice
                invoice = Invoice(
                    id=creditnote_id,
                    invoice_number=cn_data.get('creditnote_number', ''),
                    invoice_date=cn_date,
                    due_date=cn_date,
                    customer_id=str(cn_data.get('customer_id', '')),
                    customer_name=cn_data.get('customer_name', ''),
                    customer_email=cn_data.get('email', ''),
                    currency_code=cn_data.get('currency_code', 'NOK'),
                    sub_total=float(cn_data.get('sub_total', 0)),
                    tax_total=float(cn_data.get('tax_total', 0)),
                    total=float(cn_data.get('total', 0)),
                    balance=float(cn_data.get('balance', 0)),
                    status=cn_data.get('status', 'closed').lower(),
                    transaction_type='creditnote',
                    created_time=cn_date,
                    updated_time=cn_date,
                )
                session.add(invoice)

                # Process line items (negative amounts)
                line_items = cn_data.get('invoice_items', [])
                creditnote_has_valid_items = False

                for item in line_items:
                    item_name = item.get('name', '') or item.get('item_name', '')
                    item_code = item.get('code', '') or item.get('item_code', '')
                    item_desc = item.get('description', '')

                    # Filter using parameters mapping (same as CSV import)
                    if item_name not in periodization_map:
                        filtered_hardware_count += 1
                        continue  # Skip items not in allowed revenue groups

                    price = -abs(float(item.get('price', 0)))  # Negative for credit note
                    quantity = int(item.get('quantity', 1))
                    item_total = -abs(float(item.get('item_total', price * quantity)))

                    # Get periodization from parameters mapping (AUTHORITATIVE)
                    period_months = periodization_map[item_name]

                    # Calculate MRR (negative for credit note)
                    mrr_per_month = item_total / period_months

                    # IMPORTANT: Credit notes must have proper periods to affect MRR correctly
                    # Calculate period from credit note date + period_months (same as CSV import)
                    period_start_date = cn_date
                    period_end_date = period_start_date + pd.DateOffset(months=period_months) - pd.DateOffset(days=1)

                    # Get vessel information from custom fields
                    vessel_name = ''
                    call_sign = ''
                    custom_fields = item.get('custom_fields', [])
                    for cf in custom_fields:
                        if cf.get('label') == 'Fartøy':
                            vessel_name = str(cf.get('value', ''))
                        elif cf.get('label') == 'Radiokallesignal':
                            call_sign = str(cf.get('value', ''))

                    line_item = InvoiceLineItem(
                        invoice_id=creditnote_id,
                        item_id=str(item.get('item_id', '')),
                        product_id=str(item.get('product_id', '')),
                        subscription_id=str(item.get('subscription_id', '')),
                        name=item_name,
                        description=item_desc,
                        code=item_code,
                        unit=item.get('unit', ''),
                        vessel_name=vessel_name,
                        call_sign=call_sign,
                        price=price,
                        quantity=quantity,
                        item_total=item_total,
                        tax_percentage=float(item.get('tax_percentage', 0)),
                        tax_name=item.get('tax_name', ''),
                        period_start_date=period_start_date,
                        period_end_date=period_end_date,
                        period_months=period_months,
                        mrr_per_month=mrr_per_month,
                    )
                    session.add(line_item)
                    total_line_items += 1
                    creditnote_has_valid_items = True

                if creditnote_has_valid_items:
                    imported_count += 1

                # Commit every 100 transactions
                if (imported_count - len(invoice_list)) % 100 == 0:
                    await session.commit()
                    print(f"    Credit Notes: {idx}/{len(creditnote_list)} ({(idx/len(creditnote_list)*100):.1f}%), Total line items: {total_line_items}")

            except Exception as e:
                print(f"    [ERROR] Credit Note {idx}: {e}")
                error_count += 1
                continue

        # Final commit
        await session.commit()

        print(f"\n  [OK] Import complete")
        print(f"    Imported: {imported_count} transactions")
        print(f"    Filtered out (hardware/other): {filtered_hardware_count} items")
        print(f"    Skipped: {skipped_count}")
        print(f"    Errors: {error_count}")
        print(f"    Total line items: {total_line_items}")

    # Step 6: Generate snapshots
    print("\n[5] GENERATING MONTHLY SNAPSHOTS")
    print("-"*80)

    from dateutil.relativedelta import relativedelta
    async with AsyncSessionLocal() as session:
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

    print()
    print("="*80)
    print("IMPORT COMPLETE")
    print("="*80)
    print(f"Transactions imported: {imported_count}")
    print(f"Line items imported: {total_line_items}")
    print(f"Snapshots generated: {len(snapshots_created)}")


if __name__ == "__main__":
    asyncio.run(import_from_api())
