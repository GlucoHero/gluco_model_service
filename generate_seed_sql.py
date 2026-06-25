"""
Generates seed_glucose.sql — a ready-to-run SQL script that inserts 288
CGM readings (one every 5 min, 24 h) for samerA@gmail.com's child.
Paste or run this file in pgAdmin 4 → Query Tool against the 'glucohero' database.
"""
import uuid, math, random
from datetime import datetime, timedelta, timezone

random.seed(42)

now_utc = datetime.now(timezone.utc).replace(microsecond=0)
window_start = now_utc - timedelta(hours=24)

def glucose_at_hour(h):
    base = 120.0
    if 5 <= h < 8:
        base += 30 * ((h - 5) / 3)
    if 8 <= h < 10.5:
        t = (h - 8) / 2.5
        base += 80 * math.sin(math.pi * t)
    if 10.5 <= h < 12:
        base = 120 + 10 * (1 - (h - 10.5) / 1.5)
    if 12 <= h < 14.5:
        t = (h - 12) / 2.5
        base += 65 * math.sin(math.pi * t)
    if 14.5 <= h < 18:
        base = 115 + 5 * (1 - (h - 14.5) / 3.5)
    if 18 <= h < 20.5:
        t = (h - 18) / 2.5
        base += 70 * math.sin(math.pi * t)
    if 20.5 <= h < 24:
        base = 120 - 5 * ((h - 20.5) / 3.5)
    base += random.gauss(0, 4)
    return round(max(55.0, min(300.0, base)), 2)

rows = []
for i in range(288):
    t = window_start + timedelta(minutes=5 * i)
    h = t.hour + t.minute / 60.0
    val = glucose_at_hour(h)
    is_abnormal = val < 70 or val > 180
    rows.append((str(uuid.uuid4()), t.strftime('%Y-%m-%d %H:%M:%S+00'), val, is_abnormal))

lines = []
lines.append("-- ============================================================")
lines.append("-- GlucoHero — seed 288 CGM readings for samerA@gmail.com")
lines.append(f"-- Generated : {now_utc.isoformat()}")
lines.append("-- Run this in pgAdmin 4 > Query Tool (database: glucohero)")
lines.append("-- ============================================================")
lines.append("")
lines.append("DO $$")
lines.append("DECLARE")
lines.append("    v_child_id UUID;")
lines.append("BEGIN")
lines.append("")
lines.append("    -- 1. Resolve child ID from email")
lines.append("    SELECT c.id INTO v_child_id")
lines.append("    FROM children c")
lines.append("    JOIN users u ON c.user_id = u.id")
lines.append("    WHERE LOWER(u.email) = LOWER('samerA@gmail.com')")
lines.append("      AND u.deleted_at IS NULL")
lines.append("      AND c.deleted_at IS NULL")
lines.append("    LIMIT 1;")
lines.append("")
lines.append("    IF v_child_id IS NULL THEN")
lines.append("        RAISE EXCEPTION 'No child found for samerA@gmail.com';")
lines.append("    END IF;")
lines.append("")
lines.append("    RAISE NOTICE 'Seeding child: %', v_child_id;")
lines.append("")
lines.append("    -- 2. Clear existing readings in the 24-hour window")
lines.append(f"    DELETE FROM glucose_readings")
lines.append(f"    WHERE child_id = v_child_id")
lines.append(f"      AND reading_time >= '{window_start.strftime('%Y-%m-%d %H:%M:%S+00')}'")
lines.append(f"      AND deleted_at IS NULL;")
lines.append("")
lines.append("    -- 3. Insert 288 readings (one every 5 minutes)")
lines.append("    INSERT INTO glucose_readings")
lines.append("        (id, reading_time, value, unit, reading_source,")
lines.append("         is_fasting, meal_related, is_abnormal, child_id,")
lines.append("         created_at, updated_at,")
lines.append("         alert_sent, is_correction_check, correction_attempt, hospital_alert_sent)")
lines.append("    VALUES")

value_rows = []
for (rid, ts, val, abnormal) in rows:
    abn = 'TRUE' if abnormal else 'FALSE'
    value_rows.append(
        f"        ('{rid}', '{ts}', {val}, 'mg/dL', 'cgm',"
        f" FALSE, FALSE, {abn}, v_child_id,"
        f" NOW(), NOW(),"
        f" FALSE, FALSE, 0, FALSE)"
    )
lines.append(",\n".join(value_rows) + ";")
lines.append("")
lines.append(f"    RAISE NOTICE 'Done — inserted 288 readings for child %', v_child_id;")
lines.append("")
lines.append("END $$;")

sql = "\n".join(lines)

out_path = r"C:\Users\ASUS\Desktop\GlucoHero\gluco_model_service\seed_glucose.sql"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(sql)

print(f"SQL file written to: {out_path}")
print(f"Window : {window_start.strftime('%Y-%m-%d %H:%M')} UTC  ->  {now_utc.strftime('%Y-%m-%d %H:%M')} UTC")
print(f"Readings: {len(rows)}")
vals = [r[2] for r in rows]
print(f"Glucose range: {min(vals):.1f} – {max(vals):.1f} mg/dL  avg={sum(vals)/len(vals):.1f}")
