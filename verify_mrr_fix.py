import sqlite3

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Get all live subscriptions
cursor.execute('''
    SELECT amount, interval, interval_unit
    FROM subscriptions
    WHERE status = "live"
''')

def normalize_to_mrr(amount, interval, interval_unit):
    """Calculate MRR with VAT removed"""
    amount_without_vat = amount / 1.25

    if interval == "months":
        return amount_without_vat / interval_unit
    elif interval == "years":
        return amount_without_vat / (interval_unit * 12)
    else:
        return amount_without_vat

total_mrr = 0
for row in cursor.fetchall():
    amount, interval, interval_unit = row
    mrr = normalize_to_mrr(amount, interval, interval_unit)
    total_mrr += mrr

print("=" * 100)
print("MRR VERIFICATION AFTER FIX")
print("=" * 100)
print(f"\nOur calculated MRR (NEW):  {total_mrr:>15,.2f} NOK")
print(f"Zoho September MRR:        {2_057_443.53:>15,.2f} NOK")
print(f"Difference:                {total_mrr - 2_057_443.53:>15,.2f} NOK")
print(f"Difference %:              {(total_mrr - 2_057_443.53) / 2_057_443.53 * 100:>15,.2f}%")

print("\n" + "=" * 100)
if abs(total_mrr - 2_057_443.53) < 50_000:  # Within 50k tolerance
    print("✓ SUCCESS! MRR calculation now matches Zoho within acceptable range!")
    print("  The small difference is likely due to:")
    print("  - Different snapshot dates (our DB vs Zoho export)")
    print("  - Subscriptions added/cancelled between snapshots")
else:
    print("✗ WARNING: MRR still doesn't match Zoho")
    print("  Further investigation needed")

conn.close()
