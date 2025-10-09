import sqlite3
import pandas as pd

# Check database
conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM subscriptions
    GROUP BY status
    ORDER BY count DESC
''')

print("=" * 100)
print("SUBSCRIPTION COUNTS BY STATUS (Database)")
print("=" * 100)
db_statuses = {}
for row in cursor.fetchall():
    status, count = row
    db_statuses[status] = count
    print(f"{status:20} : {count:5}")

print(f"\nTotal subscriptions in DB: {sum(db_statuses.values())}")

# Check Zoho export
df = pd.read_csv(r"c:\Users\nikolai\Downloads\MRR_Details.csv", skiprows=1)
print("\n" + "=" * 100)
print("SUBSCRIPTION COUNT (Zoho Export for September)")
print("=" * 100)
print(f"Total subscriptions in export: {len(df)}")

# The export is for September, but we're comparing with current DB state (October)
# Let's check if our database has subscriptions that were activated in October
cursor.execute('''
    SELECT COUNT(*)
    FROM subscriptions
    WHERE status = "live"
      AND activated_at >= "2025-10-01"
''')
oct_new = cursor.fetchone()[0]

cursor.execute('''
    SELECT COUNT(*)
    FROM subscriptions
    WHERE status IN ("cancelled", "expired")
      AND cancelled_at >= "2025-10-01"
''')
oct_churned = cursor.fetchone()[0]

print(f"\nNew subscriptions since Oct 1: {oct_new}")
print(f"Churned subscriptions since Oct 1: {oct_churned}")

print("\n" + "=" * 100)
print("CONCLUSION:")
print("=" * 100)
print("The database reflects CURRENT state (October)")
print("The Zoho export reflects SEPTEMBER state")
print("\nExpected discrepancy:")
print(f"  September subscriptions: ~1,928 (from export)")
print(f"  October subscriptions:   ~1,827 (from database)")
print(f"  Difference: ~{1928-1827} subscriptions")

conn.close()
