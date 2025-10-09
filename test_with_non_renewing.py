import sqlite3

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

def normalize_to_mrr(amount, interval, interval_unit):
    """Calculate MRR with VAT removed"""
    amount_without_vat = amount / 1.25

    if interval == "months":
        return amount_without_vat / interval_unit
    elif interval == "years":
        return amount_without_vat / (interval_unit * 12)
    else:
        return amount_without_vat

print("=" * 100)
print("MRR CALCULATION WITH DIFFERENT STATUS COMBINATIONS")
print("=" * 100)

# Test 1: Only "live"
cursor.execute('''
    SELECT amount, interval, interval_unit
    FROM subscriptions
    WHERE status = "live"
''')

mrr_live_only = sum(normalize_to_mrr(amount, interval, interval_unit) for amount, interval, interval_unit in cursor.fetchall())

# Test 2: "live" + "non_renewing"
cursor.execute('''
    SELECT amount, interval, interval_unit
    FROM subscriptions
    WHERE status IN ("live", "non_renewing")
''')

mrr_with_non_renewing = sum(normalize_to_mrr(amount, interval, interval_unit) for amount, interval, interval_unit in cursor.fetchall())

# Test 3: "live" + "non_renewing" + "future"
cursor.execute('''
    SELECT amount, interval, interval_unit
    FROM subscriptions
    WHERE status IN ("live", "non_renewing", "future")
''')

mrr_with_all = sum(normalize_to_mrr(amount, interval, interval_unit) for amount, interval, interval_unit in cursor.fetchall())

zoho_mrr = 2_057_443.53

print(f"\nZoho September MRR:          {zoho_mrr:>15,.2f} NOK")
print("\n" + "-" * 100)
print(f"Live only:                   {mrr_live_only:>15,.2f} NOK | Diff: {mrr_live_only - zoho_mrr:>12,.2f} ({(mrr_live_only/zoho_mrr-1)*100:>6.2f}%)")
print(f"Live + Non-renewing:         {mrr_with_non_renewing:>15,.2f} NOK | Diff: {mrr_with_non_renewing - zoho_mrr:>12,.2f} ({(mrr_with_non_renewing/zoho_mrr-1)*100:>6.2f}%)")
print(f"Live + Non-renewing + Future:{mrr_with_all:>15,.2f} NOK | Diff: {mrr_with_all - zoho_mrr:>12,.2f} ({(mrr_with_all/zoho_mrr-1)*100:>6.2f}%)")

print("\n" + "=" * 100)
best_match = min(
    [(abs(mrr_live_only - zoho_mrr), "live only")],
    [(abs(mrr_with_non_renewing - zoho_mrr), "live + non_renewing")],
    [(abs(mrr_with_all - zoho_mrr), "live + non_renewing + future")]
)
print(f"Best match: {best_match[1]}")
print(f"Difference: {best_match[0]:,.2f} NOK ({best_match[0]/zoho_mrr*100:.2f}%)")

conn.close()
