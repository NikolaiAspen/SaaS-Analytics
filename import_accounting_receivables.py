"""
Import Accounting Receivable Details from Excel files

This script imports accounting's "Receivable Details" Excel reports
and stores them in the database as the "ultimate source of truth" for MRR.

Usage:
    python import_accounting_receivables.py <file_path>
    python import_accounting_receivables.py excel/RD/*.xlsx  # Batch import
"""

import asyncio
import sys
import re
from pathlib import Path
from datetime import datetime
from dateutil import parser as date_parser
import pandas as pd

from database import AsyncSessionLocal
from models.accounting import AccountingReceivableItem
from services.product_config import ProductConfigService
from sqlalchemy import delete, select
from models.product_config import ProductConfiguration


def should_be_12_months(item_name: str) -> bool:
    """
    Check if this product should be periodized for 12 months regardless of Excel data

    Products that are ALWAYS 12 months:
    - All "oppgradering" products (EXCEPT those with "(mnd)" in name)
    - VMS sporingstrafikk products (EXCEPT those with "(mnd)" in name)
    - "30 dager ERS" products (EXCEPT those with "(mnd)" in name)

    Products with "(mnd)" in name are MONTHLY and should NOT be forced to 12 months.
    """
    if not item_name or pd.isna(item_name):
        return False

    item_lower = str(item_name).lower()

    # IMPORTANT: Products with "(mnd)" are monthly subscriptions - do NOT force to 12 months
    if "(mnd)" in item_lower or "(månedlig)" in item_lower:
        return False

    # All "oppgradering" products (without "(mnd)") are 12 months
    if "oppgradering" in item_lower:
        return True

    # VMS sporingstrafikk products (without "(mnd)") are 12 months
    if "sporingstrafikk vms gprs" in item_lower:
        return True

    # 30 dager ERS products (without "(mnd)") are actually annual subscriptions
    if "30 dager ers" in item_lower or "ers 30 dager" in item_lower or "ers inkl. sporing 30 dager" in item_lower:
        return True

    return False


def parse_period_from_description(description: str, item_name: str = "") -> tuple:
    """
    Parse billing period from description field

    Returns: (start_date, end_date, months)
    """
    if not description or pd.isna(description):
        # Try to infer from item_name
        if "(år)" in str(item_name).lower() or "(årlig)" in str(item_name).lower():
            return None, None, 12
        elif "(mnd)" in str(item_name).lower() or "(månedlig)" in str(item_name).lower():
            return None, None, 1
        return None, None, 1

    description = str(description)

    try:
        # Pattern: "Gjelder perioden DD MMM YYYY til DD MMM YYYY"
        pattern = r'(\d{1,2}\s+\w+\s+\d{4})\s+til\s+(\d{1,2}\s+\w+\s+\d{4})'
        match = re.search(pattern, description, re.IGNORECASE)

        if match:
            start_str = match.group(1)
            end_str = match.group(2)

            start_date = date_parser.parse(start_str, dayfirst=True)
            end_date = date_parser.parse(end_str, dayfirst=True)

            # Calculate months
            months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
            if end_date.day >= start_date.day:
                months += 1
            months = max(1, months)

            return start_date, end_date, months

    except Exception as e:
        print(f"Warning: Failed to parse period from description: {description[:100]}")
        print(f"  Error: {e}")

    # Fallback: try to infer from item_name
    if "(år)" in str(item_name).lower() or "(årlig)" in str(item_name).lower():
        return None, None, 12
    elif "(mnd)" in str(item_name).lower() or "(månedlig)" in str(item_name).lower():
        return None, None, 1

    return None, None, 1


async def import_accounting_excel(file_path: str, source_month: str = None):
    """
    Import accounting receivable details from Excel file

    Args:
        file_path: Path to Excel file
        source_month: Optional month in YYYY-MM format (will be inferred from filename if not provided)
    """
    print(f"\n{'='*120}")
    print(f"IMPORTING ACCOUNTING RECEIVABLE DETAILS")
    print(f"File: {file_path}")
    print(f"{'='*120}")

    # Read Excel file
    print("\n[1/5] Reading Excel file...")
    df = pd.read_excel(file_path)

    # First row contains column names
    col_names = df.iloc[0].tolist()
    df = pd.read_excel(file_path, skiprows=1, header=None)
    df.columns = col_names

    # Remove the duplicate header row
    df = df[df['transaction_type'] != 'transaction_type']

    print(f"  [OK] {len(df)} rows loaded")

    # Infer source_month from filename if not provided
    if not source_month:
        # Try to extract month from filename: "Receivable Details sept 25 (5).xlsx" -> "2025-09"
        filename = Path(file_path).stem.lower()

        month_map = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }

        for month_abbr, month_num in month_map.items():
            if month_abbr in filename:
                # Try to find year
                year_match = re.search(r'\b(20)?(\d{2})\b', filename)
                if year_match:
                    year = year_match.group(2)
                    if len(year) == 2:
                        year = f"20{year}"
                    source_month = f"{year}-{month_num}"
                    break

        if not source_month:
            print(f"  [WARNING] Could not infer source_month from filename, using current month")
            source_month = datetime.utcnow().strftime("%Y-%m")

    print(f"  [OK] Source month: {source_month}")

    # Delete existing data for this month
    print(f"\n[2/6] Cleaning existing data for {source_month}...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(AccountingReceivableItem).where(
                AccountingReceivableItem.source_month == source_month
            )
        )
        await session.commit()
        print(f"  [OK] Deleted {result.rowcount} existing rows")

    # Load product configurations from database
    print(f"\n[3/6] Loading product configurations...")
    product_configs = {}
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ProductConfiguration))
        configs = result.scalars().all()
        for config in configs:
            product_configs[config.product_name] = config
        print(f"  [OK] Loaded {len(product_configs)} product configurations")

    # Parse and prepare data
    print(f"\n[4/6] Parsing data and calculating MRR...")
    items = []
    skipped = 0

    # Convert to list of dicts to avoid pandas Series issues
    rows = df.to_dict('records')

    for idx, row in enumerate(rows):
        try:
            # Parse dates
            transaction_date = None
            trans_date_val = row.get('transaction_date', None)
            if trans_date_val is not None and not pd.isna(trans_date_val):
                try:
                    transaction_date = pd.to_datetime(trans_date_val)
                except:
                    pass

            created_time = None
            created_time_val = row.get('created_time', None)
            if created_time_val is not None and not pd.isna(created_time_val):
                try:
                    created_time = pd.to_datetime(created_time_val)
                except:
                    pass

            # Parse period from description
            description_val = row.get('description', '')
            item_name_val = row.get('item_name', '')

            # Convert to string, handling pandas NaN
            if pd.isna(description_val):
                description = ''
            else:
                description = str(description_val)

            if pd.isna(item_name_val):
                item_name = ''
            else:
                item_name = str(item_name_val)

            start_date, end_date, period_months = parse_period_from_description(description, item_name)

            # DATABASE OVERRIDE: Check if product has manual configuration
            if item_name in product_configs:
                config = product_configs[item_name]
                period_months = config.period_months
                # Recalculate end_date based on configured period
                if start_date:
                    end_date = start_date + pd.DateOffset(months=period_months, days=-1)
            # AUTOMATIC OVERRIDE: Force 12 months for specific products (if no manual config)
            elif should_be_12_months(item_name):
                period_months = 12
                # Recalculate end_date based on 12 months
                if start_date:
                    end_date = start_date + pd.DateOffset(months=12, days=-1)

            # If we have transaction_date but no start_date, use transaction_date as start
            if transaction_date and not start_date:
                start_date = transaction_date
                # Calculate end_date based on period_months
                if period_months > 1:
                    end_date = start_date + pd.DateOffset(months=period_months, days=-1)
                else:
                    end_date = start_date + pd.DateOffset(months=1, days=-1)

            # Calculate MRR
            bcy_total_with_tax_val = row.get('bcy_total_with_tax', 0)
            bcy_total_with_tax = float(bcy_total_with_tax_val) if not pd.isna(bcy_total_with_tax_val) else 0.0

            # Remove VAT (25%)
            bcy_total_excl_vat = bcy_total_with_tax / 1.25

            # Calculate MRR per month
            mrr_per_month = bcy_total_excl_vat / period_months if period_months > 0 else bcy_total_excl_vat

            # For credit notes, MRR should be negative
            transaction_type = str(row.get('transaction_type', ''))
            if transaction_type == 'creditnote':
                mrr_per_month = -abs(mrr_per_month)

            # Parse numeric fields safely
            quantity_ordered_val = row.get('quantity_ordered', 0)
            quantity_ordered = float(quantity_ordered_val) if not pd.isna(quantity_ordered_val) else 0.0

            bcy_item_price_val = row.get('bcy_item_price', 0)
            bcy_item_price = float(bcy_item_price_val) if not pd.isna(bcy_item_price_val) else 0.0

            bcy_total_val = row.get('bcy_total', 0)
            bcy_total = float(bcy_total_val) if not pd.isna(bcy_total_val) else 0.0

            bcy_tax_amount_val = row.get('bcy_tax_amount', 0)
            bcy_tax_amount = float(bcy_tax_amount_val) if not pd.isna(bcy_tax_amount_val) else 0.0

            product_name_val = row.get('product_name', '')
            product_name = str(product_name_val)[:500] if not pd.isna(product_name_val) else ''

            # Create item
            item = AccountingReceivableItem(
                item_id=str(row.get('item_id', '')),
                transaction_id=str(row.get('transaction_id', '')),
                transaction_number=str(row.get('transaction_number', '')),
                customer_id=str(row.get('customer_id', '')),
                product_id=str(row.get('product_id', '')),
                transaction_type=transaction_type,
                transaction_date=transaction_date,
                status=str(row.get('status', '')),
                item_name=item_name[:500],
                product_name=product_name,
                description=description[:5000] if description else None,
                quantity_ordered=quantity_ordered,
                bcy_item_price=bcy_item_price,
                bcy_total=bcy_total,
                bcy_total_with_tax=bcy_total_with_tax,
                bcy_tax_amount=bcy_tax_amount,
                customer_name=str(row.get('customer_name', ''))[:500],
                company_name=str(row.get('company_name', ''))[:500],
                vessel_name=str(row.get('invoice.CF.Fartøy', ''))[:500] if not pd.isna(row.get('invoice.CF.Fartøy')) else None,
                call_sign=str(row.get('invoice.CF.Radiokallesignal', ''))[:100] if not pd.isna(row.get('invoice.CF.Radiokallesignal')) else None,
                customer_reference=str(row.get('invoice.CF.Deres ref', ''))[:500] if not pd.isna(row.get('invoice.CF.Deres ref')) else None,
                period_start_date=start_date,
                period_end_date=end_date,
                period_months=period_months,
                mrr_per_month=mrr_per_month,
                source_file=str(Path(file_path).name),
                source_month=source_month,
                created_time=created_time,
                created_by=str(row.get('created_by', ''))[:200] if not pd.isna(row.get('created_by')) else None,
            )

            items.append(item)

        except Exception as e:
            print(f"  [ERROR] Failed to parse row {idx}: {e}")
            skipped += 1
            continue

    print(f"  [OK] Parsed {len(items)} items ({skipped} skipped)")

    # Batch insert
    print(f"\n[5/6] Inserting into database...")
    async with AsyncSessionLocal() as session:
        session.add_all(items)
        await session.commit()
        print(f"  [OK] Inserted {len(items)} items")

    # Summary
    print(f"\n[6/6] Summary:")
    invoices = [i for i in items if i.transaction_type == 'invoice']
    creditnotes = [i for i in items if i.transaction_type == 'creditnote']

    total_invoice_mrr = sum(i.mrr_per_month for i in invoices if i.mrr_per_month)
    total_creditnote_mrr = sum(i.mrr_per_month for i in creditnotes if i.mrr_per_month)
    total_mrr = total_invoice_mrr + total_creditnote_mrr

    print(f"  - Invoices: {len(invoices)} items, {total_invoice_mrr:,.2f} NOK MRR")
    print(f"  - Credit notes: {len(creditnotes)} items, {total_creditnote_mrr:,.2f} NOK MRR")
    print(f"  - Total MRR: {total_mrr:,.2f} NOK")
    print(f"  - Unique customers: {len(set(i.customer_name for i in items))}")

    print(f"\n{'='*120}")
    print(f"[SUCCESS] Import complete for {source_month}")
    print(f"{'='*120}\n")

    # Return import statistics
    return {
        "source_month": source_month,
        "total_items": len(items),
        "invoice_count": len(invoices),
        "creditnote_count": len(creditnotes),
        "invoice_mrr": round(total_invoice_mrr, 2),
        "creditnote_mrr": round(total_creditnote_mrr, 2),
        "total_mrr": round(total_mrr, 2),
        "unique_customers": len(set(i.customer_name for i in items)),
    }


async def batch_import(file_pattern: str):
    """
    Batch import multiple Excel files

    Args:
        file_pattern: Glob pattern for files (e.g., "excel/RD/*.xlsx")
    """
    from glob import glob

    files = glob(file_pattern)

    if not files:
        print(f"No files found matching pattern: {file_pattern}")
        return

    print(f"Found {len(files)} files to import")

    for i, file_path in enumerate(files, 1):
        print(f"\n\n{'#'*120}")
        print(f"File {i}/{len(files)}: {Path(file_path).name}")
        print(f"{'#'*120}")

        try:
            await import_accounting_excel(file_path)
        except Exception as e:
            print(f"[ERROR] Failed to import {file_path}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n\n{'='*120}")
    print(f"BATCH IMPORT COMPLETE")
    print(f"Successfully imported {len(files)} files")
    print(f"{'='*120}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_accounting_receivables.py <file_path>")
        print("       python import_accounting_receivables.py 'excel/RD/*.xlsx'  # Batch import")
        sys.exit(1)

    file_path = sys.argv[1]

    # Check if it's a glob pattern
    if '*' in file_path:
        asyncio.run(batch_import(file_path))
    else:
        asyncio.run(import_accounting_excel(file_path))
