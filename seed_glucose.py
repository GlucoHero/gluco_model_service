"""
Seed 288 CGM glucose readings (one per 5 minutes, covering 24 hours) for the
child whose user email is samerA@gmail.com.

The glucose trace is a realistic Type-1 diabetic child pattern:
  - Stable overnight baseline ~120 mg/dL
  - Dawn phenomenon rise 06:00-08:00
  - Post-breakfast spike ~200 mg/dL then correction back to range
  - Post-lunch spike ~185 mg/dL
  - Post-dinner spike ~190 mg/dL
  - Gradual return to baseline overnight

Existing readings in the last 24-hour window are removed first so the model
always gets exactly 288 evenly-spaced points.
"""

import uuid
import math
import random
import psycopg2
from datetime import datetime, timedelta, timezone

# ── DB connection (from .env) ─────────────────────────────────────────────────
conn = psycopg2.connect(
    host="127.0.0.1",
    port=5432,
    dbname="glucohero",
    user="postgres",
    password="postgres",
)
conn.autocommit = False
cur = conn.cursor()

# ── 1. Find the child ID for samerA@gmail.com ─────────────────────────────────
cur.execute("""
    SELECT c.id, u.email, u.first_name, u.last_name
    FROM children c
    JOIN users u ON c.user_id = u.id
    WHERE LOWER(u.email) = LOWER(%s)
      AND u.deleted_at IS NULL
      AND c.deleted_at IS NULL
    LIMIT 1
""", ("samerA@gmail.com",))

row = cur.fetchone()
if not row:
    print("ERROR: No child found with email samerA@gmail.com")
    print("Checking what users exist...")
    cur.execute("SELECT email, role FROM users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 20")
    for r in cur.fetchall():
        print(" ", r)
    conn.close()
    exit(1)

child_id, email, first_name, last_name = row
print(f"Found child: {first_name} {last_name} <{email}>  id={child_id}\n")

# ── 2. Remove existing readings in the last 24 h to start clean ───────────────
now_utc = datetime.now(timezone.utc)
window_start = now_utc - timedelta(hours=24)

cur.execute("""
    DELETE FROM glucose_readings
    WHERE child_id = %s
      AND reading_time >= %s
      AND deleted_at IS NULL
""", (child_id, window_start))
deleted = cur.rowcount
print(f"Removed {deleted} existing reading(s) in the 24-hour window.")

# ── 3. Generate 288 realistic glucose values ──────────────────────────────────
random.seed(42)

def glucose_at_hour(h: float) -> float:
    """
    Returns a baseline glucose value (mg/dL) for hour h (0-24) mimicking a
    typical T1D child day: stable overnight, dawn rise, 3 meal spikes.
    """
    # Overnight baseline
    base = 120.0

    # Dawn phenomenon: gentle rise 05:00-08:00
    if 5 <= h < 8:
        base += 30 * ((h - 5) / 3)

    # Breakfast spike 08:00-10:30  (peak ~200 at 09:00, back to ~130 by 10:30)
    if 8 <= h < 10.5:
        t = (h - 8) / 2.5
        base += 80 * math.sin(math.pi * t)

    # Mid-morning dip back toward 120
    if 10.5 <= h < 12:
        base = 120 + 10 * (1 - (h - 10.5) / 1.5)

    # Lunch spike 12:00-14:30 (peak ~185 at 13:00)
    if 12 <= h < 14.5:
        t = (h - 12) / 2.5
        base += 65 * math.sin(math.pi * t)

    # Afternoon recovery 14:30-18:00
    if 14.5 <= h < 18:
        base = 115 + 5 * (1 - (h - 14.5) / 3.5)

    # Dinner spike 18:00-20:30 (peak ~190 at 19:00)
    if 18 <= h < 20.5:
        t = (h - 18) / 2.5
        base += 70 * math.sin(math.pi * t)

    # Evening wind-down 20:30-24:00
    if 20.5 <= h < 24:
        base = 120 - 5 * ((h - 20.5) / 3.5)

    # Small random noise ±4 mg/dL
    base += random.gauss(0, 4)

    return round(max(55.0, min(300.0, base)), 2)

readings = []
for i in range(288):
    t = window_start + timedelta(minutes=5 * i)
    h = (t.hour + t.minute / 60.0)
    value = glucose_at_hour(h)
    is_abnormal = value < 70 or value > 180
    readings.append((
        str(uuid.uuid4()),   # id
        t,                   # reading_time
        value,               # value
        "mg/dL",             # unit
        "cgm",               # reading_source
        False,               # is_fasting
        False,               # meal_related
        is_abnormal,         # is_abnormal
        child_id,            # child_id
        now_utc,             # created_at
        now_utc,             # updated_at
    ))

# ── 4. Bulk insert ────────────────────────────────────────────────────────────
cur.executemany("""
    INSERT INTO glucose_readings
        (id, reading_time, value, unit, reading_source,
         is_fasting, meal_related, is_abnormal, child_id,
         created_at, updated_at,
         alert_sent, is_correction_check, correction_attempt, hospital_alert_sent)
    VALUES
        (%s, %s, %s, %s, %s,
         %s, %s, %s, %s,
         %s, %s,
         FALSE, FALSE, 0, FALSE)
""", readings)

conn.commit()
print(f"Inserted {len(readings)} glucose readings for child {child_id}.\n")

# ── 5. Quick summary ─────────────────────────────────────────────────────────
values = [r[2] for r in readings]
in_range = sum(1 for v in values if 70 <= v <= 180)
print("========== SEEDED DATA SUMMARY ==========")
print(f"  Child email     : {email}")
print(f"  Child ID        : {child_id}")
print(f"  Readings        : {len(readings)} (one every 5 min, 24 h)")
print(f"  Window          : {window_start.strftime('%Y-%m-%d %H:%M')} UTC")
print(f"                    -> {now_utc.strftime('%Y-%m-%d %H:%M')} UTC")
print(f"  Min glucose     : {min(values):.1f} mg/dL")
print(f"  Max glucose     : {max(values):.1f} mg/dL")
print(f"  Average glucose : {sum(values)/len(values):.1f} mg/dL")
print(f"  In range (70-180): {in_range}/{len(readings)} ({100*in_range//len(readings)}%)")
print("=========================================")
print("\nThe forecast model should now be able to predict. Trigger")
print("GET /api/v1/glucose/child/<childId>/forecast in the app.")

cur.close()
conn.close()
