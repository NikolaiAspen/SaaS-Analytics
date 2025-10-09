import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Get all live subscriptions
cursor.execute('''
    SELECT id, customer_name, amount, interval, interval_unit, currency_code
    FROM subscriptions
    WHERE status = "live"
    ORDER BY amount DESC
    LIMIT 20
''')

print("Top 20 highest MRR subscriptions:")
print("=" * 100)

def normalize_to_mrr(amount, interval, interval_unit):
    """Calculate monthly MRR from subscription amount"""
    if interval == "months":
        return amount / interval_unit
    elif interval == "years":
        return amount / (interval_unit * 12)
    else:
        return amount

total_mrr = 0
for row in cursor.fetchall():
    sub_id, name, amount, interval, interval_unit, currency = row
    mrr = normalize_to_mrr(amount, interval, interval_unit)
    total_mrr += mrr
    print(f"{name[:40]:40} | {amount:10.2f} {currency} | {interval:8} {interval_unit} | MRR: {mrr:10.2f}")

print("=" * 100)

# Get total statistics
cursor.execute('''
    SELECT
        COUNT(*) as count,
        interval,
        interval_unit,
        SUM(amount) as total_amount
    FROM subscriptions
    WHERE status = "live"
    GROUP BY interval, interval_unit
    ORDER BY interval, interval_unit
''')

print("\nBreakdown by billing interval:")
print("-" * 80)
grand_total_mrr = 0

for row in cursor.fetchall():
    count, interval, interval_unit, total_amount = row
    # Calculate total MRR for this group
    group_mrr = normalize_to_mrr(total_amount, interval, interval_unit)
    grand_total_mrr += group_mrr
    print(f"{interval:10} every {interval_unit:2} | Count: {count:4} | Total: {total_amount:12,.2f} | MRR: {group_mrr:12,.2f}")

print("-" * 80)
print(f"TOTAL MRR: {grand_total_mrr:,.2f} NOK")
print(f"Expected (from Zoho): 2,057,856.53 NOK")
print(f"Difference: {grand_total_mrr - 2057856.53:,.2f} NOK")
print(f"Difference %: {(grand_total_mrr - 2057856.53) / 2057856.53 * 100:.2f}%")

# Check if amounts might include VAT
print("\n" + "=" * 100)
print("Checking if amounts include 25% VAT (Norwegian MVA):")
mrr_without_vat = grand_total_mrr / 1.25
print(f"MRR without VAT (÷ 1.25): {mrr_without_vat:,.2f} NOK")
print(f"Difference from Zoho: {mrr_without_vat - 2057856.53:,.2f} NOK")

conn.close()
