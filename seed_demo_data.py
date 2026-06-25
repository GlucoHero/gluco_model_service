"""
Seed 7 days of realistic demo data for the child samerA@gmail.com:
  - Glucose readings  : one CGM point every 5 min  (7 × 288 = 2016 readings)
  - Meals             : breakfast / lunch / dinner / snack each day (28 meals)
  - Insulin doses     : morning basal + post-meal boluses each day  (28 doses)

Existing data in the 7-day window is removed first so re-running is idempotent.
"""

import uuid
import math
import random
import json
import psycopg2
from datetime import datetime, timedelta, timezone

# ── DB connection ─────────────────────────────────────────────────────────────
conn = psycopg2.connect(
    host="127.0.0.1",
    port=5432,
    dbname="glucohero",
    user="postgres",
    password="postgres",
)
conn.autocommit = False
cur = conn.cursor()

# ── 1. Resolve child ──────────────────────────────────────────────────────────
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
    cur.execute("SELECT email, role FROM users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 20")
    for r in cur.fetchall():
        print(" ", r)
    conn.close()
    exit(1)

child_id, email, first_name, last_name = row
print(f"Found child: {first_name} {last_name} <{email}>  id={child_id}\n")

# ── 2. Define time window (last 7 days) ───────────────────────────────────────
now_utc      = datetime.now(timezone.utc)
window_start = now_utc - timedelta(days=7)

print(f"Window : {window_start.strftime('%Y-%m-%d %H:%M')} UTC  ->  {now_utc.strftime('%Y-%m-%d %H:%M')} UTC\n")

# ── 3. Clear existing data in window ─────────────────────────────────────────
cur.execute("DELETE FROM glucose_readings WHERE child_id = %s AND reading_time >= %s", (child_id, window_start))
print(f"Removed {cur.rowcount} existing glucose reading(s).")

cur.execute("DELETE FROM meals WHERE child_id = %s AND meal_time >= %s", (child_id, window_start))
print(f"Removed {cur.rowcount} existing meal(s).")

cur.execute("DELETE FROM insulin_doses WHERE child_id = %s AND dose_time >= %s", (child_id, window_start))
print(f"Removed {cur.rowcount} existing insulin dose(s).\n")

random.seed(99)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. GLUCOSE READINGS  (288 per day × 7 days)
# ═══════════════════════════════════════════════════════════════════════════════

def glucose_at_hour(h: float, day_variation: float = 0.0) -> float:
    """
    Realistic T1D child glucose trace for one day (hour 0-24).
    day_variation shifts the baseline slightly to make each day unique.
    """
    base = 120.0 + day_variation

    # Dawn phenomenon 05:00-08:00
    if 5 <= h < 8:
        base += 30 * ((h - 5) / 3)

    # Breakfast spike 07:30-10:00
    if 7.5 <= h < 10.0:
        t = (h - 7.5) / 2.5
        base += 78 * math.sin(math.pi * t)

    # Mid-morning correction dip
    if 10.0 <= h < 12.0:
        base = (120 + day_variation) + 8 * (1 - (h - 10.0) / 2.0)

    # Lunch spike 12:00-14:30
    if 12.0 <= h < 14.5:
        t = (h - 12.0) / 2.5
        base += 65 * math.sin(math.pi * t)

    # Afternoon recovery 14:30-18:00
    if 14.5 <= h < 18.0:
        base = (115 + day_variation) + 5 * (1 - (h - 14.5) / 3.5)

    # Dinner spike 18:00-20:30
    if 18.0 <= h < 20.5:
        t = (h - 18.0) / 2.5
        base += 72 * math.sin(math.pi * t)

    # Evening wind-down 20:30-24:00
    if 20.5 <= h < 24.0:
        base = (120 + day_variation) - 6 * ((h - 20.5) / 3.5)

    # ±5 mg/dL noise
    base += random.gauss(0, 5)
    return round(max(55.0, min(300.0, base)), 2)


glucose_rows = []
total_points = 7 * 288

for day_offset in range(7):
    day_variation = random.uniform(-8, 8)
    day_start = window_start + timedelta(days=day_offset)

    for i in range(288):
        t = day_start + timedelta(minutes=5 * i)
        if t > now_utc:
            break
        h = t.hour + t.minute / 60.0
        val = glucose_at_hour(h, day_variation)
        is_abnormal = val < 70 or val > 180
        is_fasting = (0.0 <= h < 7.5)
        meal_related = (7.5 <= h < 10.5) or (12.0 <= h < 15.0) or (18.0 <= h < 21.0)

        glucose_rows.append((
            str(uuid.uuid4()),  # id
            t,                  # reading_time
            val,                # value
            "mg/dL",            # unit
            "cgm",              # reading_source
            is_fasting,         # is_fasting
            meal_related,       # meal_related
            is_abnormal,        # is_abnormal
            child_id,           # child_id
            now_utc,            # created_at
            now_utc,            # updated_at
        ))

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
""", glucose_rows)

print(f"Inserted {len(glucose_rows)} glucose readings.")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. MEALS  (4 per day × 7 days)
# ═══════════════════════════════════════════════════════════════════════════════

MEAL_TEMPLATES = {
    "breakfast": [
        {
            "description": "Oatmeal with banana and milk",
            "totalCarbs": 62.0, "totalCalories": 380.0, "totalProtein": 12.0, "totalFat": 8.0,
            "items": [
                {"name": "Oatmeal", "quantity": 1, "unit": "cup", "carbs": 27, "calories": 150, "protein": 5, "fat": 3},
                {"name": "Banana", "quantity": 1, "unit": "medium", "carbs": 27, "calories": 105, "protein": 1, "fat": 0},
                {"name": "Whole milk", "quantity": 200, "unit": "ml", "carbs": 8, "calories": 125, "protein": 6, "fat": 5},
            ],
            "hour": 7.5,
        },
        {
            "description": "Scrambled eggs with toast and orange juice",
            "totalCarbs": 48.0, "totalCalories": 420.0, "totalProtein": 18.0, "totalFat": 14.0,
            "items": [
                {"name": "Scrambled eggs", "quantity": 2, "unit": "eggs", "carbs": 2, "calories": 180, "protein": 12, "fat": 10},
                {"name": "Whole wheat toast", "quantity": 2, "unit": "slices", "carbs": 26, "calories": 140, "protein": 6, "fat": 2},
                {"name": "Orange juice", "quantity": 200, "unit": "ml", "carbs": 20, "calories": 100, "protein": 0, "fat": 2},
            ],
            "hour": 7.5,
        },
        {
            "description": "Pancakes with honey and strawberries",
            "totalCarbs": 75.0, "totalCalories": 490.0, "totalProtein": 10.0, "totalFat": 12.0,
            "items": [
                {"name": "Pancakes", "quantity": 3, "unit": "pieces", "carbs": 54, "calories": 300, "protein": 8, "fat": 9},
                {"name": "Honey", "quantity": 1, "unit": "tbsp", "carbs": 17, "calories": 64, "protein": 0, "fat": 0},
                {"name": "Strawberries", "quantity": 100, "unit": "g", "carbs": 4, "calories": 32, "protein": 2, "fat": 3},
            ],
            "hour": 8.0,
        },
    ],
    "lunch": [
        {
            "description": "Grilled chicken rice bowl with vegetables",
            "totalCarbs": 65.0, "totalCalories": 520.0, "totalProtein": 35.0, "totalFat": 10.0,
            "items": [
                {"name": "White rice", "quantity": 1, "unit": "cup", "carbs": 45, "calories": 200, "protein": 4, "fat": 0},
                {"name": "Grilled chicken", "quantity": 120, "unit": "g", "carbs": 0, "calories": 200, "protein": 28, "fat": 8},
                {"name": "Mixed vegetables", "quantity": 100, "unit": "g", "carbs": 10, "calories": 50, "protein": 3, "fat": 1},
                {"name": "Olive oil", "quantity": 1, "unit": "tsp", "carbs": 0, "calories": 40, "protein": 0, "fat": 5},
            ],
            "hour": 12.5,
        },
        {
            "description": "Whole wheat pasta with tomato sauce and cheese",
            "totalCarbs": 72.0, "totalCalories": 550.0, "totalProtein": 22.0, "totalFat": 14.0,
            "items": [
                {"name": "Whole wheat pasta", "quantity": 80, "unit": "g", "carbs": 56, "calories": 290, "protein": 12, "fat": 2},
                {"name": "Tomato sauce", "quantity": 150, "unit": "g", "carbs": 12, "calories": 70, "protein": 3, "fat": 2},
                {"name": "Mozzarella cheese", "quantity": 40, "unit": "g", "carbs": 4, "calories": 100, "protein": 7, "fat": 7},
            ],
            "hour": 13.0,
        },
        {
            "description": "Lentil soup with pita bread and yogurt",
            "totalCarbs": 68.0, "totalCalories": 460.0, "totalProtein": 20.0, "totalFat": 8.0,
            "items": [
                {"name": "Lentil soup", "quantity": 300, "unit": "ml", "carbs": 36, "calories": 200, "protein": 14, "fat": 2},
                {"name": "Pita bread", "quantity": 1, "unit": "piece", "carbs": 28, "calories": 165, "protein": 6, "fat": 2},
                {"name": "Plain yogurt", "quantity": 100, "unit": "g", "carbs": 4, "calories": 60, "protein": 5, "fat": 3},
            ],
            "hour": 12.0,
        },
    ],
    "snack": [
        {
            "description": "Apple with peanut butter",
            "totalCarbs": 30.0, "totalCalories": 220.0, "totalProtein": 5.0, "totalFat": 8.0,
            "items": [
                {"name": "Apple", "quantity": 1, "unit": "medium", "carbs": 25, "calories": 95, "protein": 0, "fat": 0},
                {"name": "Peanut butter", "quantity": 1, "unit": "tbsp", "carbs": 5, "calories": 95, "protein": 5, "fat": 8},
            ],
            "hour": 15.5,
        },
        {
            "description": "Whole grain crackers with cheese",
            "totalCarbs": 22.0, "totalCalories": 180.0, "totalProtein": 6.0, "totalFat": 7.0,
            "items": [
                {"name": "Whole grain crackers", "quantity": 6, "unit": "pieces", "carbs": 18, "calories": 120, "protein": 3, "fat": 3},
                {"name": "Cheddar cheese", "quantity": 30, "unit": "g", "carbs": 4, "calories": 120, "protein": 7, "fat": 10},
            ],
            "hour": 16.0,
        },
    ],
    "dinner": [
        {
            "description": "Baked salmon with sweet potato and broccoli",
            "totalCarbs": 55.0, "totalCalories": 580.0, "totalProtein": 40.0, "totalFat": 18.0,
            "items": [
                {"name": "Salmon fillet", "quantity": 150, "unit": "g", "carbs": 0, "calories": 280, "protein": 35, "fat": 14},
                {"name": "Sweet potato", "quantity": 150, "unit": "g", "carbs": 34, "calories": 130, "protein": 2, "fat": 0},
                {"name": "Broccoli", "quantity": 100, "unit": "g", "carbs": 7, "calories": 35, "protein": 3, "fat": 0},
                {"name": "Olive oil", "quantity": 1, "unit": "tbsp", "carbs": 0, "calories": 120, "protein": 0, "fat": 14},
            ],
            "hour": 18.5,
        },
        {
            "description": "Beef stew with rice and salad",
            "totalCarbs": 70.0, "totalCalories": 620.0, "totalProtein": 38.0, "totalFat": 16.0,
            "items": [
                {"name": "Beef stew", "quantity": 200, "unit": "g", "carbs": 15, "calories": 280, "protein": 30, "fat": 12},
                {"name": "White rice", "quantity": 1, "unit": "cup", "carbs": 45, "calories": 200, "protein": 4, "fat": 0},
                {"name": "Green salad", "quantity": 100, "unit": "g", "carbs": 5, "calories": 30, "protein": 2, "fat": 2},
                {"name": "Dressing", "quantity": 1, "unit": "tbsp", "carbs": 5, "calories": 60, "protein": 0, "fat": 6},
            ],
            "hour": 19.0,
        },
        {
            "description": "Grilled chicken shawarma wrap",
            "totalCarbs": 60.0, "totalCalories": 550.0, "totalProtein": 35.0, "totalFat": 14.0,
            "items": [
                {"name": "Chicken shawarma", "quantity": 150, "unit": "g", "carbs": 5, "calories": 250, "protein": 28, "fat": 10},
                {"name": "Flatbread wrap", "quantity": 1, "unit": "piece", "carbs": 35, "calories": 200, "protein": 6, "fat": 2},
                {"name": "Hummus", "quantity": 40, "unit": "g", "carbs": 10, "calories": 80, "protein": 3, "fat": 4},
                {"name": "Vegetables", "quantity": 80, "unit": "g", "carbs": 10, "calories": 35, "protein": 2, "fat": 1},
            ],
            "hour": 18.5,
        },
    ],
}

def calc_insulin(carbs: float) -> float:
    """Simplified carb-to-insulin ratio: 1 unit per 15 g carbs."""
    return round(carbs / 15.0, 2)

meal_rows = []

for day_offset in range(7):
    day_start = window_start + timedelta(days=day_offset)

    for meal_type in ["breakfast", "lunch", "snack", "dinner"]:
        templates = MEAL_TEMPLATES[meal_type]
        tmpl = templates[day_offset % len(templates)]

        base_hour = tmpl["hour"] + random.uniform(-0.25, 0.25)
        meal_time = day_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=base_hour)

        if meal_time > now_utc:
            continue

        carbs = tmpl["totalCarbs"] + random.uniform(-5, 5)
        carbs = round(max(10.0, carbs), 2)
        calc_ins = calc_insulin(carbs)
        pre_glucose = round(glucose_at_hour(base_hour - 0.25), 2)
        expected_min = round(pre_glucose + carbs * 0.8, 2)
        expected_max = round(pre_glucose + carbs * 1.6, 2)

        meal_rows.append((
            str(uuid.uuid4()),                       # id
            meal_type,                               # meal_type
            meal_time,                               # meal_time
            tmpl["description"],                     # description
            carbs,                                   # total_carbs
            round(tmpl["totalCalories"] + random.uniform(-20, 20), 2),   # total_calories
            round(tmpl.get("totalProtein", 0), 2),   # total_protein
            round(tmpl.get("totalFat", 0), 2),       # total_fat
            calc_ins,                                # calculated_insulin
            round(min(expected_min, 180), 2),        # expected_post_meal_glucose_min
            round(min(expected_max, 250), 2),        # expected_post_meal_glucose_max
            pre_glucose,                             # pre_meal_glucose
            False,                                   # requires_recheck
            None,                                    # recheck_time
            None,                                    # photo_url
            False,                                   # is_ai_recognized
            None,                                    # ai_confidence
            json.dumps(tmpl.get("items", [])),       # items (jsonb)
            child_id,                                # child_id
            now_utc,                                 # created_at
            now_utc,                                 # updated_at
        ))

cur.executemany("""
    INSERT INTO meals
        (id, meal_type, meal_time, description,
         total_carbs, total_calories, total_protein, total_fat,
         calculated_insulin,
         expected_post_meal_glucose_min, expected_post_meal_glucose_max,
         pre_meal_glucose,
         requires_recheck, recheck_time,
         photo_url, is_ai_recognized, ai_confidence,
         items,
         child_id, created_at, updated_at)
    VALUES
        (%s, %s, %s, %s,
         %s, %s, %s, %s,
         %s,
         %s, %s,
         %s,
         %s, %s,
         %s, %s, %s,
         %s,
         %s, %s, %s)
""", meal_rows)

print(f"Inserted {len(meal_rows)} meals.")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. INSULIN DOSES  (4 per day × 7 days)
# ═══════════════════════════════════════════════════════════════════════════════

INSULIN_SCHEDULE = [
    # (label, hour, insulin_type, is_correction, meal_related, site, reason)
    ("morning_basal",  7.0,  "glargine",  False, False, "abdomen",      "Morning Basal"),
    ("breakfast_bolus", 7.5, "lispro",    False, True,  "upper_arm",    "After Meal"),
    ("lunch_bolus",    12.5, "lispro",    False, True,  "thigh",        "After Meal"),
    ("dinner_bolus",   18.5, "lispro",    False, True,  "abdomen",      "After Meal"),
]

insulin_rows = []

for day_offset in range(7):
    day_start = window_start + timedelta(days=day_offset)

    for label, base_hour, ins_type, is_correction, meal_related, site, reason in INSULIN_SCHEDULE:
        hour_jitter = base_hour + random.uniform(-0.2, 0.2)
        dose_time = day_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=hour_jitter)

        if dose_time > now_utc:
            continue

        # Dose amount: basal ~16 U, boluses depend on meal carbs
        if ins_type == "glargine":
            dose = round(random.uniform(14.0, 18.0), 2)
        else:
            # Bolus: random carb estimate for the linked meal
            carbs_estimate = random.uniform(50, 80)
            dose = round(carbs_estimate / 15.0 + random.uniform(-0.5, 0.5), 2)
            dose = max(1.0, dose)

        glucose_before = round(glucose_at_hour(hour_jitter - 0.1), 2)

        insulin_rows.append((
            str(uuid.uuid4()),   # id
            dose,                # dose
            "units",             # unit
            ins_type,            # insulin_type
            dose_time,           # dose_time
            site,                # injection_site
            is_correction,       # is_correction_dose
            meal_related,        # meal_related
            glucose_before,      # glucose_before
            "NovoRapid" if ins_type == "lispro" else "Lantus",  # brand
            reason,              # reason
            None,                # notes
            child_id,            # child_id
            now_utc,             # created_at
            now_utc,             # updated_at
        ))

cur.executemany("""
    INSERT INTO insulin_doses
        (id, dose, unit, insulin_type, dose_time,
         injection_site, is_correction_dose, meal_related,
         glucose_before, brand, reason, notes,
         child_id, created_at, updated_at)
    VALUES
        (%s, %s, %s, %s, %s,
         %s, %s, %s,
         %s, %s, %s, %s,
         %s, %s, %s)
""", insulin_rows)

print(f"Inserted {len(insulin_rows)} insulin doses.")

# ── Commit ────────────────────────────────────────────────────────────────────
conn.commit()

# ── Summary ───────────────────────────────────────────────────────────────────
glucose_vals = [r[2] for r in glucose_rows]
in_range = sum(1 for v in glucose_vals if 70 <= v <= 180)

print("\n========== DEMO DATA SUMMARY ==========")
print(f"  Child         : {first_name} {last_name} <{email}>")
print(f"  Child ID      : {child_id}")
print(f"  Window        : last 7 days")
print(f"")
print(f"  Glucose readings : {len(glucose_rows)}")
print(f"    Min            : {min(glucose_vals):.1f} mg/dL")
print(f"    Max            : {max(glucose_vals):.1f} mg/dL")
print(f"    Avg            : {sum(glucose_vals)/len(glucose_vals):.1f} mg/dL")
print(f"    In range 70-180: {in_range}/{len(glucose_rows)} ({100*in_range//len(glucose_rows)}%)")
print(f"")
print(f"  Meals inserted   : {len(meal_rows)}")
print(f"    Breakfasts     : {sum(1 for m in meal_rows if m[1]=='breakfast')}")
print(f"    Lunches        : {sum(1 for m in meal_rows if m[1]=='lunch')}")
print(f"    Snacks         : {sum(1 for m in meal_rows if m[1]=='snack')}")
print(f"    Dinners        : {sum(1 for m in meal_rows if m[1]=='dinner')}")
print(f"")
print(f"  Insulin doses    : {len(insulin_rows)}")
print(f"    Basal (glargine): {sum(1 for r in insulin_rows if r[3]=='glargine')}")
print(f"    Bolus (lispro)  : {sum(1 for r in insulin_rows if r[3]=='lispro')}")
print("========================================")

cur.close()
conn.close()
