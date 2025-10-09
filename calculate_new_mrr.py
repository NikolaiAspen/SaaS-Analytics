"""
Calculate New MRR by comparing month-over-month MRR Details files
New MRR = subscriptions that exist in current month but NOT in previous month
"""
import pandas as pd
from datetime import datetime

def get_month_from_filename(filename):
    """Extract month from various filename formats"""
    # Handle formats like "Oct2024", "Nov2024", "MRR Details (1)"
    import re

    if 'Oct2024' in filename:
        return '2024-10'
    elif 'Nov2024' in filename:
        return '2024-11'
    elif 'Dec2024' in filename:
        return '2024-12'
    elif 'MRR Details.xlsx' in filename:
        return '2025-02'  # Based on the date column we saw
    elif 'MRR Details (1)' in filename:
        return '2025-03'
    # Add more mappings as needed
    return None

def load_mrr_details(file_path):
    """Load MRR details file"""
    df = pd.read_excel(file_path, skiprows=1)

    # Get date from first row
    date = pd.to_datetime(df['date'].iloc[0])
    month = date.strftime('%Y-%m')

    return month, df

def calculate_new_mrr(current_file, previous_file):
    """Calculate New MRR by comparing two months"""

    current_month, current_df = load_mrr_details(current_file)
    previous_month, previous_df = load_mrr_details(previous_file)

    print(f"\nComparing {previous_month} -> {current_month}")
    print(f"Previous month subscriptions: {len(previous_df)}")
    print(f"Current month subscriptions: {len(current_df)}")

    # Find subscriptions that exist in current but not in previous
    previous_subs = set(previous_df['subscription_id'].tolist())
    current_subs = set(current_df['subscription_id'].tolist())

    new_subs = current_subs - previous_subs

    # Calculate total MRR from new subscriptions
    new_mrr_df = current_df[current_df['subscription_id'].isin(new_subs)]
    new_mrr = new_mrr_df['mrr'].sum()

    print(f"New subscriptions: {len(new_subs)}")
    print(f"New MRR: {new_mrr:,.2f} kr")

    if len(new_subs) > 0:
        print(f"\nNew subscriptions:")
        for _, row in new_mrr_df.head(10).iterrows():
            print(f"  - {row['customer_name']:40s} {row['plan_name']:40s} {row['mrr']:>10,.0f} kr")

    return {
        'current_month': current_month,
        'previous_month': previous_month,
        'new_subscriptions': len(new_subs),
        'new_mrr': float(new_mrr)
    }

# Calculate for available months
print("Calculating New MRR from month-over-month changes...")
print("="*80)

# Oct -> Nov
result1 = calculate_new_mrr('excel/Nov2024.xlsx', 'excel/Oct2024.xlsx')

# Nov -> Dec
result2 = calculate_new_mrr('excel/Dec2024.xlsx', 'excel/Nov2024.xlsx')

# Dec -> Feb (assuming MRR Details.xlsx is Feb)
# Note: We're missing Jan data
result3 = calculate_new_mrr('excel/MRR Details.xlsx', 'excel/Dec2024.xlsx')

# Feb -> Mar
result4 = calculate_new_mrr('excel/MRR Details (1).xlsx', 'excel/MRR Details.xlsx')

print("\n" + "="*80)
print("Summary:")
print("="*80)
for result in [result1, result2, result3, result4]:
    print(f"{result['current_month']}: {result['new_mrr']:>12,.0f} kr from {result['new_subscriptions']:>3} new subscriptions")
