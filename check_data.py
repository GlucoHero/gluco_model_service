import psycopg2
from datetime import datetime, timedelta, timezone

conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='glucohero', user='postgres', password='postgres')
cur = conn.cursor()

cur.execute("SELECT c.id FROM children c JOIN users u ON c.user_id=u.id WHERE LOWER(u.email)=LOWER('samerA@gmail.com') LIMIT 1")
child_id = cur.fetchone()[0]
print('Child ID:', child_id)

now = datetime.now(timezone.utc)
start_24h = now - timedelta(hours=24)
start_7d  = now - timedelta(days=7)

cur.execute('SELECT COUNT(*) FROM glucose_readings WHERE child_id=%s AND reading_time >= %s', (child_id, start_24h))
print('Glucose readings (last 24h):', cur.fetchone()[0])

cur.execute('SELECT COUNT(*) FROM glucose_readings WHERE child_id=%s AND reading_time >= %s', (child_id, start_7d))
print('Glucose readings (last 7d):', cur.fetchone()[0])

cur.execute('SELECT COUNT(*) FROM meals WHERE child_id=%s AND meal_time >= %s', (child_id, start_7d))
print('Meals (last 7d):', cur.fetchone()[0])

cur.execute('SELECT COUNT(*) FROM insulin_doses WHERE child_id=%s AND dose_time >= %s', (child_id, start_7d))
print('Insulin doses (last 7d):', cur.fetchone()[0])

cur.execute('SELECT MIN(reading_time), MAX(reading_time) FROM glucose_readings WHERE child_id=%s', (child_id,))
row = cur.fetchone()
print('Glucose time range:', row[0], '->', row[1])

conn.close()
