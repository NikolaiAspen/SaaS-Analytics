import sqlite3
import json

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Get a sample yearly subscription to see all fields
cursor.execute('''
    SELECT *
    FROM subscriptions
    WHERE status = "live" AND interval = "years"
    LIMIT 1
''')

columns = [description[0] for description in cursor.description]
row = cursor.fetchone()

print("Sample yearly subscription (all fields):")
print("=" * 100)
for col, val in zip(columns, row):
    print(f"{col:20}: {val}")

print("\n" + "=" * 100)
print("\nKey question: Does Zoho provide an 'mrr' field in the API response?")
print("If yes, we should use that instead of calculating from 'amount'")
print("\nFrom the database, we only have:")
print("  - amount: The subscription amount (yearly or monthly)")
print("  - interval: 'months' or 'years'")
print("  - interval_unit: 1 (always)")
print("\nWe calculate: MRR = amount / 12 (for yearly)")
print("But Zoho might calculate it differently!")

conn.close()
