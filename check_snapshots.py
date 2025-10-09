import sqlite3

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT id, snapshot_date, mrr, arr, total_customers, active_subscriptions, created_at
    FROM metrics_snapshots
    ORDER BY created_at DESC
    LIMIT 5
''')

print("Recent metrics snapshots:")
print("-" * 100)
for row in cursor.fetchall():
    snap_id, snap_date, mrr, arr, customers, subs, created = row
    print(f"ID: {snap_id}")
    print(f"  Snapshot date: {snap_date}")
    print(f"  MRR: {mrr:,.2f} NOK")
    print(f"  ARR: {arr:,.2f} NOK")
    print(f"  Customers: {customers}")
    print(f"  Subscriptions: {subs}")
    print(f"  Created at: {created}")
    print()

conn.close()
