import pandas as pd
import sqlite3
from datetime import datetime

# Read Zoho's monthly MRR report
df = pd.read_csv(r"c:\Users\nikolai\Downloads\Monthly_MRR.csv", skiprows=1)

print("=" * 100)
print("ZOHO MONTHLY MRR vs OUR CALCULATION")
print("=" * 100)

# Clean up column names
df.columns = ['date', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7', 'col8', 'net_mrr']

# Convert to proper types
df['date'] = pd.to_datetime(df['date'])
df['net_mrr'] = pd.to_numeric(df['net_mrr'], errors='coerce')

print("\nZoho's MRR by month:")
print(df[['date', 'net_mrr']])

# Now calculate our MRR for each month
conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

def normalize_to_mrr(amount, interval, interval_unit):
    """Calculate MRR with VAT removed and non_renewing included"""
    amount_without_vat = amount / 1.25

    if interval == "months":
        return amount_without_vat / interval_unit
    elif interval == "years":
        return amount_without_vat / (interval_unit * 12)
    else:
        return amount_without_vat

def calculate_mrr_for_date(end_date):
    """Calculate MRR as of a specific date"""
    cursor.execute('''
        SELECT amount, interval, interval_unit
        FROM subscriptions
        WHERE status IN ("live", "non_renewing")
          AND activated_at <= ?
          AND (cancelled_at IS NULL OR cancelled_at > ?)
    ''', (end_date, end_date))

    return sum(normalize_to_mrr(amount, interval, interval_unit) for amount, interval, interval_unit in cursor.fetchall())

print("\n" + "=" * 100)
print("COMPARISON:")
print("=" * 100)
print(f"{'Month':<12} {'Zoho MRR':>15} {'Our MRR':>15} {'Difference':>15} {'Diff %':>10}")
print("-" * 100)

for idx, row in df.iterrows():
    zoho_mrr = row['net_mrr']
    if pd.isna(zoho_mrr):
        continue

    # Calculate our MRR for end of this month
    month_date = row['date']

    # Get last day of month
    from dateutil.relativedelta import relativedelta
    last_day = month_date + relativedelta(months=1) - relativedelta(days=1)
    last_day_str = last_day.strftime('%Y-%m-%d 23:59:59')

    our_mrr = calculate_mrr_for_date(last_day_str)

    diff = our_mrr - zoho_mrr
    diff_pct = (diff / zoho_mrr * 100) if zoho_mrr > 0 else 0

    print(f"{month_date.strftime('%Y-%m'):<12} {zoho_mrr:>15,.2f} {our_mrr:>15,.2f} {diff:>15,.2f} {diff_pct:>9.2f}%")

conn.close()

print("\n" + "=" * 100)
print("NOTES:")
print("- Our database reflects current state (October 2025)")
print("- Historical months might differ due to data changes over time")
print("- October 2025 should be the most accurate comparison")
