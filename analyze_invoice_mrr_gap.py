import pandas as pd
import sys
from datetime import datetime
from dateutil.relativedelta import relativedelta

print("=" * 100)
print("COMPREHENSIVE INVOICE MRR ANALYSIS")
print("Comparing Invoice-based MRR vs Subscription-based MRR")
print("=" * 100)

# Files to analyze
files = {
    '2024': r"C:/Users/nikolai/Code/Saas_analyse/excel/Receivable Details (3).xlsx",
    '2025': r"C:/Users/nikolai/Code/Saas_analyse/excel/Receivable Details (1).xlsx"
}

all_data = []

for period, file_path in files.items():
    try:
        print(f"\nLoading {period} data from {file_path}...")

        # Read Excel file
        df = pd.read_excel(file_path, skiprows=0)

        # Use first row as column names
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)

        # Handle duplicate column names
        cols = pd.Series(df.columns)
        for dup in cols[cols.duplicated()].unique():
            cols[cols[cols == dup].index.values.tolist()] = [dup + '_' + str(i) if i != 0 else dup for i in range(sum(cols == dup))]
        df.columns = cols

        print(f"  Loaded {len(df)} rows")
        all_data.append(df)

    except Exception as e:
        print(f"  ERROR: {e}")
        continue

# Combine all data
df_combined = pd.concat(all_data, ignore_index=True)

print(f"\n{'='*100}")
print(f"COMBINED DATA SUMMARY")
print(f"{'='*100}")
print(f"Total rows: {len(df_combined)}")
print(f"Date range: {df_combined['transaction_date'].min()} to {df_combined['transaction_date'].max()}")

# Convert numeric columns
numeric_cols = ['bcy_item_price', 'fcy_item_price', 'bcy_total', 'fcy_total',
                'bcy_total_with_tax', 'fcy_total_with_tax', 'bcy_tax_amount', 'fcy_tax_amount',
                'quantity_ordered']

for col in numeric_cols:
    if col in df_combined.columns:
        df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce')

# Convert transaction_date to datetime
df_combined['transaction_date'] = pd.to_datetime(df_combined['transaction_date'], errors='coerce')

print(f"\nTransaction types: {df_combined['transaction_type'].value_counts().to_dict()}")
print(f"Statuses: {df_combined['status'].value_counts().to_dict()}")

# Financial summary
print(f"\n{'='*100}")
print(f"TOTAL FINANCIAL SUMMARY (All Time)")
print(f"{'='*100}")
print(f"Total invoiced (excl VAT): {df_combined['bcy_total'].sum():,.2f} NOK")
print(f"Total invoiced (incl VAT): {df_combined['bcy_total_with_tax'].sum():,.2f} NOK")
print(f"Total VAT: {df_combined['bcy_tax_amount'].sum():,.2f} NOK")

# Separate invoices and credit notes
invoices = df_combined[df_combined['transaction_type'] == 'invoice'].copy()
creditnotes = df_combined[df_combined['transaction_type'] == 'creditnote'].copy()

print(f"\nInvoices: {len(invoices)} lines, {invoices['bcy_total'].sum():,.2f} NOK (excl VAT)")
print(f"Credit notes: {len(creditnotes)} lines, {creditnotes['bcy_total'].sum():,.2f} NOK (excl VAT)")
print(f"Net: {(invoices['bcy_total'].sum() + creditnotes['bcy_total'].sum()):,.2f} NOK")

# Monthly breakdown
print(f"\n{'='*100}")
print(f"MONTHLY BREAKDOWN (Invoice Date)")
print(f"{'='*100}")

df_combined['year_month'] = df_combined['transaction_date'].dt.to_period('M')
monthly = df_combined.groupby(['year_month', 'transaction_type']).agg({
    'bcy_total': 'sum',
    'transaction_id': 'count'
}).reset_index()

monthly_pivot = monthly.pivot_table(
    index='year_month',
    columns='transaction_type',
    values=['bcy_total', 'transaction_id'],
    fill_value=0
)

print("\nMonthly invoice amounts (excl VAT):")
print(monthly_pivot.head(20))

# Now, let's try to calculate MRR from these invoices
# This is tricky because we need to extract period information
print(f"\n{'='*100}")
print(f"ANALYZING INVOICE DESCRIPTIONS FOR PERIODS")
print(f"{'='*100}")

# Look at item descriptions to understand period structure
sample_descriptions = df_combined[['item_name', 'description', 'product_name']].drop_duplicates().head(50)
print("\nSample item descriptions:")
print(sample_descriptions.to_string())

# Try to extract periods from description
# Looks like format: "Gjelder perioden DD MMM YYYY til DD MMM YYYY"
import re

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
# Apply function and expand results into separate columns
period_info = df_combined['description'].apply(extract_period_months).apply(pd.Series)
period_info.columns = ['period_months', 'period_start', 'period_end']
df_combined = pd.concat([df_combined, period_info], axis=1)

# Check how many we extracted
extracted = df_combined['period_months'].notna().sum()
print(f"Successfully extracted period info from {extracted} / {len(df_combined)} rows ({100*extracted/len(df_combined):.1f}%)")

# For rows without period info, try to infer from product_name
# (år) = 12 months, (mnd) = 1 month
def infer_period_from_name(row):
    if pd.notna(row['period_months']):
        return row['period_months']

    name = str(row['item_name'])
    if '(år)' in name or '(År)' in name:
        return 12
    elif '(mnd)' in name or '(Mnd)' in name:
        return 1
    elif '60 dager' in name:
        return 2  # ~60 days = ~2 months
    elif '30 dager' in name:
        return 1  # ~30 days = ~1 month

    return None

df_combined['period_months_inferred'] = df_combined.apply(infer_period_from_name, axis=1)
inferred = df_combined['period_months_inferred'].notna().sum()
print(f"After inference: {inferred} / {len(df_combined)} rows have period info ({100*inferred/len(df_combined):.1f}%)")

# Now calculate period_start and period_end for rows where we have period_months but no dates
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

# Convert to datetime to ensure proper comparison
df_combined['period_start'] = pd.to_datetime(df_combined['period_start'], errors='coerce')
df_combined['period_end'] = pd.to_datetime(df_combined['period_end'], errors='coerce')

# Check how many now have dates
with_dates = df_combined['period_start'].notna().sum()
print(f"After calculation: {with_dates} / {len(df_combined)} rows have period dates ({100*with_dates/len(df_combined):.1f}%)")

# Calculate MRR per line item
def calculate_line_mrr(row):
    """Calculate MRR for a single invoice line"""
    amount_excl_vat = row['bcy_total']
    period_months = row['period_months_inferred']

    if pd.isna(amount_excl_vat) or pd.isna(period_months) or period_months == 0:
        return 0

    # MRR = amount / months
    mrr = amount_excl_vat / period_months

    return mrr

df_combined['line_mrr'] = df_combined.apply(calculate_line_mrr, axis=1)

print(f"\n{'='*100}")
print(f"INVOICE-BASED MRR CALCULATION")
print(f"{'='*100}")

# For each month, calculate active MRR
# A line contributes to MRR in a month if its period covers that month

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
    if month.year == 2024 and month.month <= 3:  # Show first few months
        print(f"  {month_str}: {mrr:,.0f} NOK ({count} total: {inv_count} inv, {cn_count} cn)")
    elif month.year == 2025:  # Show 2025
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

# Save results
output_file = 'invoice_mrr_analysis.csv'
mrr_df.to_csv(output_file, index=False)
print(f"\nResults saved to: {output_file}")

print(f"\n{'='*100}")
print(f"KEY FINDINGS")
print(f"{'='*100}")
print(f"1. We have {len(df_combined)} invoice lines covering {df_combined['transaction_date'].min()} to {df_combined['transaction_date'].max()}")
print(f"2. {100*inferred/len(df_combined):.1f}% of lines have period information extracted")
print(f"3. Invoice-based MRR can now be calculated month-by-month based on active periods")
print(f"4. This can be compared with subscription-based MRR from the database")
print(f"\nNext steps:")
print(f"  - Compare invoice-based MRR with subscription-based MRR from database")
print(f"  - Identify which customers/products cause the difference")
print(f"  - Investigate missing period information")
