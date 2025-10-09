import sqlite3

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Check a specific subscription from Zoho
cursor.execute('''
    SELECT id, customer_name, plan_name, amount, interval, interval_unit, status
    FROM subscriptions
    WHERE customer_name LIKE '%HALSTENSEN%'
    LIMIT 5
''')

print("HALSTENSEN subscriptions (example):")
print("=" * 100)
for row in cursor.fetchall():
    print(row)

# Check if there are subscriptions with interval_unit != 1
cursor.execute('''
    SELECT COUNT(*), interval, interval_unit
    FROM subscriptions
    WHERE status = "live" AND interval_unit != 1
    GROUP BY interval, interval_unit
''')

print("\nSubscriptions with interval_unit != 1:")
print("-" * 80)
for row in cursor.fetchall():
    print(f"Count: {row[0]:4} | Interval: {row[1]:10} | Interval Unit: {row[2]}")

# Check total subscriptions by status
cursor.execute('''
    SELECT status, COUNT(*), SUM(amount)
    FROM subscriptions
    GROUP BY status
    ORDER BY COUNT(*) DESC
''')

print("\nAll subscriptions by status:")
print("-" * 80)
for row in cursor.fetchall():
    status, count, total = row
    print(f"{status:20} | Count: {count:5} | Total Amount: {total:15,.2f}")

# Check if Zoho might be using a different field for MRR
print("\n" + "=" * 100)
print("Checking raw amounts from yearly subscriptions...")
cursor.execute('''
    SELECT amount, interval, interval_unit, COUNT(*) as cnt
    FROM subscriptions
    WHERE status = "live" AND interval = "years"
    GROUP BY amount, interval, interval_unit
    ORDER BY amount DESC
    LIMIT 10
''')

print("Most common yearly subscription amounts:")
for row in cursor.fetchall():
    amount, interval, interval_unit, cnt = row
    mrr = amount / (interval_unit * 12)
    print(f"{amount:10,.2f} NOK/year ({cnt:3} subs) = {mrr:10,.2f} NOK/month")

conn.close()
