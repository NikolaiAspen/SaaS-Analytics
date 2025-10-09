import sqlite3

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM subscriptions')
print(f'Total subscriptions in DB: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM subscriptions WHERE status="live"')
print(f'Live subscriptions: {cursor.fetchone()[0]}')

cursor.execute('SELECT status, COUNT(*) FROM subscriptions GROUP BY status')
print('\nSubscriptions by status:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')

cursor.execute('SELECT COUNT(DISTINCT customer_id) FROM subscriptions WHERE status="live"')
print(f'\nUnique customers with live subscriptions: {cursor.fetchone()[0]}')

cursor.execute('SELECT * FROM subscriptions WHERE status="live" LIMIT 3')
print('\nSample live subscriptions:')
columns = [description[0] for description in cursor.description]
print(f'Columns: {columns}')
for row in cursor.fetchall():
    print(row)

conn.close()
