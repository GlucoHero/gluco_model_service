"""
List users to find the right credentials
"""
import psycopg2

conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='glucohero', user='postgres', password='postgres')
cur = conn.cursor()
cur.execute("SELECT email, role FROM users WHERE deleted_at IS NULL ORDER BY role, created_at LIMIT 30")
print("email | role")
print("-" * 50)
for row in cur.fetchall():
    print(f"{row[0]} | {row[1]}")
conn.close()
