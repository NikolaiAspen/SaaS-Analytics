"""
Complete Invoice MRR Analysis - Including ALL paid/unpaid invoices and credit notes
This script uses Invoice Details (not Receivable Details) to get ALL invoices, including paid ones
"""
import pandas as pd
import asyncio
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from database import AsyncSessionLocal, init_db
from models import InvoiceMRRSnapshot
import re

print("=" * 100)
print("COMPLETE INVOICE MRR ANALYSIS")
print("Using Invoice Details (includes paid invoices) + Credit Note Details")
print("=" * 100)

# Files to analyze - Invoice line items with descriptions and periods
invoice_files = [
    'c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (3).csv',  # 2024 Jan-Jun
    'c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (2).csv',  # 2024 Jul-Dec
    'c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (1).csv',  # 2025 Jan-Apr
    'c:/Users/nikolai/Code/Saas_analyse/excel/Invoice.csv',      # 2025 May-Oct
]

creditnote_files = [
    'c:/Users/nikolai/Code/Saas_analyse/excel/Credit_Note.csv',  # All credit notes with line items
]

all_data = []

# Load Invoice line items from CSV files
print("\n" + "="*100)
print("LOADING INVOICE LINE ITEMS (CSV)")
print("="*100)

for file_path in invoice_files:
    try:
        print(f"\nLoading {file_path}...")
        df = pd.read_csv(file_path, encoding='utf-8')

        # Rename columns to match expected names
        column_mapping = {
            'Invoice Date': 'transaction_date',
            'Invoice Status': 'status',
            'Item Desc': 'description',
            'Item Name': 'item_name',
            'Item Price': 'bcy_item_price',
            'Item Total': 'bcy_total',
            'Customer Name': 'customer_name',
            'Invoice Number': 'invoice_number',
            'Invoice ID': 'invoice_id'
        }
        df = df.rename(columns=column_mapping)

        # Mark as invoice line items
        df['transaction_type'] = 'invoice'

        print(f"  Loaded {len(df)} invoice line items")
        print(f"  Statuses: {df['status'].value_counts().to_dict()}")
        print(f"  Has descriptions: {df['description'].notna().sum()} / {len(df)}")
        all_data.append(df)

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        continue

# Load Credit Note line items from CSV file
print("\n" + "="*100)
print("LOADING CREDIT NOTE LINE ITEMS (CSV)")
print("="*100)

for file_path in creditnote_files:
    try:
        print(f"\nLoading {file_path}...")
        df = pd.read_csv(file_path, encoding='utf-8')

        # Rename columns to match expected names
        column_mapping = {
            'Credit Note Date': 'transaction_date',
            'Credit Note Status': 'status',
            'Item Desc': 'description',
            'Item Name': 'item_name',
            'Item Price': 'bcy_item_price',
            'Item Total': 'bcy_total',
            'Customer Name': 'customer_name',
            'Credit Note Number': 'invoice_number',  # Use same field name for consistency
            'CreditNotes ID': 'invoice_id'
        }
        df = df.rename(columns=column_mapping)

        # Mark as credit note
        df['transaction_type'] = 'creditnote'

        print(f"  Loaded {len(df)} credit note line items")
        print(f"  Statuses: {df['status'].value_counts().to_dict()}")
        print(f"  Has descriptions: {df['description'].notna().sum()} / {len(df)}")
        all_data.append(df)

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        continue

# Combine all data
df_combined = pd.concat(all_data, ignore_index=True)

print(f"\n{'='*100}")
print(f"COMBINED DATA SUMMARY")
print(f"{'='*100}")
print(f"Total rows: {len(df_combined)}")

# Amount column should already be renamed to 'bcy_total'
amount_col = 'bcy_total'

if amount_col not in df_combined.columns:
    print(f"ERROR: Amount column '{amount_col}' not found in combined data")
    print(f"Available columns: {list(df_combined.columns[:20])}")
    exit(1)

print(f"Using amount column: {amount_col}")

# Convert numeric columns
numeric_cols = [amount_col, 'bcy_balance', 'balance', 'quantity_ordered']
for col in numeric_cols:
    if col in df_combined.columns:
        df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce')

# Convert transaction_date to datetime
df_combined['transaction_date'] = pd.to_datetime(df_combined['transaction_date'], errors='coerce')

print(f"Date range: {df_combined['transaction_date'].min()} to {df_combined['transaction_date'].max()}")
print(f"\nTransaction types: {df_combined['transaction_type'].value_counts().to_dict()}")
print(f"Statuses: {df_combined['status'].value_counts().to_dict()}")

# Financial summary
print(f"\n{'='*100}")
print(f"FINANCIAL SUMMARY")
print(f"{'='*100}")
invoices = df_combined[df_combined['transaction_type'] == 'invoice'].copy()
creditnotes = df_combined[df_combined['transaction_type'] == 'creditnote'].copy()

# For credit notes, the amount is typically positive in Zoho export, but should be negative for MRR
# Check if credit note amounts are positive (they should reduce MRR, so be negative)
if len(creditnotes) > 0 and creditnotes[amount_col].mean() > 0:
    print("Note: Credit note amounts are positive, negating them for MRR calculation...")
    # Negate in the main dataframe
    df_combined.loc[df_combined['transaction_type'] == 'creditnote', amount_col] = -df_combined.loc[df_combined['transaction_type'] == 'creditnote', amount_col]
    # Update local copy
    creditnotes[amount_col] = -creditnotes[amount_col]

print(f"Invoices: {len(invoices)} line items, {invoices[amount_col].sum():,.2f} NOK")
print(f"Credit notes: {len(creditnotes)} line items, {creditnotes[amount_col].sum():,.2f} NOK (negative)")
print(f"Net: {(invoices[amount_col].sum() + creditnotes[amount_col].sum()):,.2f} NOK")

# Extract periods from descriptions
print(f"\n{'='*100}")
print(f"EXTRACTING BILLING PERIODS FROM DESCRIPTIONS")
print(f"{'='*100}")

def extract_period_months(desc):
    """Extract number of months from description like 'Gjelder perioden 01 May 2025 til 30 Apr 2026'"""
    if pd.isna(desc):
        return None, None, None

    # Try to find date patterns
    date_pattern = r'(\d{1,2})\s+(\w+)\s+(\d{4})'
    matches = re.findall(date_pattern, str(desc))

    if len(matches) >= 2:
        try:
            # Parse start and end dates
            start_str = f"{matches[0][0]} {matches[0][1]} {matches[0][2]}"
            end_str = f"{matches[1][0]} {matches[1][1]} {matches[1][2]}"

            start_date = pd.to_datetime(start_str, format='%d %b %Y', errors='coerce')
            end_date = pd.to_datetime(end_str, format='%d %b %Y', errors='coerce')

            if pd.notna(start_date) and pd.notna(end_date):
                # Calculate difference in months
                delta = relativedelta(end_date, start_date)
                months = delta.years * 12 + delta.months + (1 if delta.days > 0 else 0)
                return months, start_date, end_date
        except:
            pass

    return None, None, None

print("\nExtracting periods from descriptions...")
period_info = df_combined['description'].apply(extract_period_months).apply(pd.Series)
period_info.columns = ['period_months', 'period_start', 'period_end']
df_combined = pd.concat([df_combined, period_info], axis=1)

# Check how many we extracted
extracted = df_combined['period_months'].notna().sum()
print(f"Successfully extracted period info from {extracted} / {len(df_combined)} rows ({100*extracted/len(df_combined):.1f}%)")

# Infer period from item_name for rows without period info
def infer_period_from_name(row):
    if pd.notna(row['period_months']):
        return row['period_months']

    name = str(row.get('item_name', ''))
    if '(år)' in name or '(År)' in name:
        return 12
    elif '(mnd)' in name or '(Mnd)' in name:
        return 1
    elif '60 dager' in name:
        return 2
    elif '30 dager' in name:
        return 1

    return None

df_combined['period_months_inferred'] = df_combined.apply(infer_period_from_name, axis=1)
inferred = df_combined['period_months_inferred'].notna().sum()
print(f"After inference: {inferred} / {len(df_combined)} rows have period info ({100*inferred/len(df_combined):.1f}%)")

# Calculate period dates for inferred periods
def calculate_period_dates(row):
    """Calculate period start/end dates based on transaction date and inferred months"""
    # If we already have dates from description extraction, keep them
    if pd.notna(row['period_start']) and pd.notna(row['period_end']):
        return row['period_start'], row['period_end']

    # If we have inferred months, calculate dates
    if pd.notna(row['period_months_inferred']) and pd.notna(row['transaction_date']):
        # Use transaction date as start
        start_date = row['transaction_date']
        # Calculate end date by adding months
        months = int(row['period_months_inferred'])
        end_date = start_date + relativedelta(months=months)
        return start_date, end_date

    return row['period_start'], row['period_end']

print("\nCalculating period dates for inferred periods...")
period_dates = df_combined.apply(calculate_period_dates, axis=1).apply(pd.Series)
period_dates.columns = ['calc_start', 'calc_end']
df_combined['period_start'] = period_dates['calc_start']
df_combined['period_end'] = period_dates['calc_end']

# Convert to datetime
df_combined['period_start'] = pd.to_datetime(df_combined['period_start'], errors='coerce')
df_combined['period_end'] = pd.to_datetime(df_combined['period_end'], errors='coerce')

with_dates = df_combined['period_start'].notna().sum()
print(f"After calculation: {with_dates} / {len(df_combined)} rows have period dates ({100*with_dates/len(df_combined):.1f}%)")

# Calculate MRR per line item
def calculate_line_mrr(row):
    """Calculate MRR for a single invoice line"""
    amount = row[amount_col]
    period_months = row['period_months_inferred']

    if pd.isna(amount) or pd.isna(period_months) or period_months == 0:
        return 0

    # MRR = amount / months
    mrr = amount / period_months

    return mrr

df_combined['line_mrr'] = df_combined.apply(calculate_line_mrr, axis=1)

print(f"\n{'='*100}")
print(f"MONTHLY MRR CALCULATION")
print(f"{'='*100}")

def calculate_monthly_mrr(df, target_month):
    """Calculate MRR for a specific month based on active invoice periods (including credit notes)"""
    target_date = pd.to_datetime(f"{target_month}-01")

    # Filter to lines where period covers target month
    # CRITICAL: Include both invoices AND credit notes for accurate MRR
    active_lines = df[
        (df['period_start'] <= target_date) &
        (df['period_end'] >= target_date) &
        (df['transaction_type'].isin(['invoice', 'creditnote']))
    ].copy()

    total_mrr = active_lines['line_mrr'].sum()
    line_count = len(active_lines)

    # Separate counts for visibility
    invoice_count = len(active_lines[active_lines['transaction_type'] == 'invoice'])
    creditnote_count = len(active_lines[active_lines['transaction_type'] == 'creditnote'])

    return total_mrr, line_count, invoice_count, creditnote_count

# Calculate MRR for recent months
months_to_check = pd.date_range(start='2024-01-01', end='2025-10-01', freq='MS')
mrr_by_month = []

print("\nCalculating invoice-based MRR by month (including credit notes)...")
for month in months_to_check:
    month_str = month.strftime('%Y-%m')
    mrr, count, inv_count, cn_count = calculate_monthly_mrr(df_combined, month_str)
    mrr_by_month.append({
        'month': month_str,
        'invoice_mrr': mrr,
        'active_lines': count,
        'invoice_lines': inv_count,
        'creditnote_lines': cn_count
    })
    if month.year >= 2025:  # Show 2025 months
        print(f"  {month_str}: {mrr:,.0f} NOK ({count} total: {inv_count} inv, {cn_count} cn)")

mrr_df = pd.DataFrame(mrr_by_month)

print(f"\n{'='*100}")
print(f"INVOICE-BASED MRR SUMMARY")
print(f"{'='*100}")
print(mrr_df.tail(12))

# Summary statistics
print(f"\nMRR Statistics:")
print(f"  Average MRR (2024): {mrr_df[mrr_df['month'].str.startswith('2024')]['invoice_mrr'].mean():,.0f} NOK")
print(f"  Latest MRR (Oct 2025): {mrr_df[mrr_df['month'] == '2025-10']['invoice_mrr'].values[0]:,.0f} NOK")
print(f"  Min MRR: {mrr_df['invoice_mrr'].min():,.0f} NOK")
print(f"  Max MRR: {mrr_df['invoice_mrr'].max():,.0f} NOK")

# Save results to CSV
output_file = 'complete_invoice_mrr_analysis.csv'
mrr_df.to_csv(output_file, index=False)
print(f"\nResults saved to: {output_file}")

# Import to database
print(f"\n{'='*100}")
print(f"IMPORTING TO DATABASE")
print(f"{'='*100}")

async def import_to_db():
    await init_db()

    async with AsyncSessionLocal() as db:
        inserted = 0
        updated = 0

        print("\nProcessing records...")
        for _, row in mrr_df.iterrows():
            month = row['month']

            # Check if record already exists
            result = await db.execute(
                select(InvoiceMRRSnapshot).where(InvoiceMRRSnapshot.month == month)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing record
                existing.mrr = float(row['invoice_mrr'])
                existing.arr = float(row['invoice_mrr']) * 12
                existing.active_lines = int(row['active_lines'])
                existing.invoice_lines = int(row['invoice_lines'])
                existing.creditnote_lines = int(row['creditnote_lines'])
                existing.source = 'invoice_details_complete'
                existing.updated_at = datetime.utcnow()
                updated += 1
                print(f"  Updated {month}: MRR={row['invoice_mrr']:,.0f} NOK ({row['active_lines']} lines: {row['invoice_lines']} inv, {row['creditnote_lines']} cn)")
            else:
                # Create new record
                snapshot = InvoiceMRRSnapshot(
                    month=month,
                    mrr=float(row['invoice_mrr']),
                    arr=float(row['invoice_mrr']) * 12,
                    active_lines=int(row['active_lines']),
                    invoice_lines=int(row['invoice_lines']),
                    creditnote_lines=int(row['creditnote_lines']),
                    source='invoice_details_complete'
                )
                db.add(snapshot)
                inserted += 1
                print(f"  Inserted {month}: MRR={row['invoice_mrr']:,.0f} NOK ({row['active_lines']} lines: {row['invoice_lines']} inv, {row['creditnote_lines']} cn)")

        # Commit changes
        await db.commit()

        print(f"\n{'='*100}")
        print(f"IMPORT COMPLETE")
        print(f"{'='*100}")
        print(f"  Inserted: {inserted} records")
        print(f"  Updated: {updated} records")
        print(f"  Total: {inserted + updated} records in database")

asyncio.run(import_to_db())

print(f"\n{'='*100}")
print(f"KEY FINDINGS")
print(f"{'='*100}")
print(f"1. Total invoices: {len(invoices)} (including {invoices[invoices['status']=='paid'].count()['status']} paid)")
print(f"2. Total credit notes: {len(creditnotes)}")
print(f"3. {100*inferred/len(df_combined):.1f}% of lines have period information")
print(f"4. Invoice-based MRR now includes ALL invoices (paid and unpaid)")
print(f"5. Credit notes are properly deducted from MRR")
print(f"\nNext steps:")
print(f"  - View results at: /api/invoices/trends")
print(f"  - Compare with subscription-based MRR")
print(f"  - Set up regular sync from Zoho API for future data")
