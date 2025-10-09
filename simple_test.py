import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Simulate SQLAlchemy query
now_str = datetime.utcnow().isoformat()
print(f"Querying with datetime: {now_str}")

cursor.execute('''
    SELECT COUNT(*)
    FROM subscriptions
    WHERE status = 'live'
      AND activated_at <= ?
      AND (cancelled_at IS NULL OR cancelled_at > ?)
''', (now_str, now_str))

count = cursor.fetchone()[0]
print(f"Live subscriptions matching criteria: {count}")

# Also check without datetime comparison
cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'live'")
total_live = cursor.fetchone()[0]
print(f"Total live subscriptions (without date filter): {total_live}")

conn.close()
