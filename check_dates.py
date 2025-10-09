import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Check activated_at dates
cursor.execute('''
    SELECT id, customer_name, activated_at, status
    FROM subscriptions
    WHERE status="live"
    ORDER BY activated_at DESC
    LIMIT 10
''')

print("Latest activated subscriptions:")
print("-" * 80)
for row in cursor.fetchall():
    sub_id, name, activated, status = row
    print(f"{name[:30]:30} | {activated} | {status}")

print("\n" + "=" * 80)
print(f"Current UTC time: {datetime.utcnow()}")
print(f"Comparing dates...")

# Check if any live subscriptions have activated_at in the future
cursor.execute('''
    SELECT COUNT(*)
    FROM subscriptions
    WHERE status="live" AND activated_at > datetime('now')
''')
future_count = cursor.fetchone()[0]
print(f"Live subscriptions with future activated_at: {future_count}")

# Check if any live subscriptions have activated_at <= now
cursor.execute('''
    SELECT COUNT(*)
    FROM subscriptions
    WHERE status="live" AND activated_at <= datetime('now')
''')
past_count = cursor.fetchone()[0]
print(f"Live subscriptions with activated_at <= now: {past_count}")

conn.close()
