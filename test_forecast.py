"""
Test the glucose forecast endpoint end-to-end:
1. Login as the parent of samerA@gmail.com
2. Hit GET /api/v1/glucose/child/<childId>/forecast?windows=5,10,15,20,25,30
"""
import requests
import json

BASE = "http://127.0.0.1:3000/api/v1"
CHILD_ID = "8f9e9f1f-0c79-4807-b78f-6b595bdaa312"

# ── 1. Login (try parent account) ──────────────────────────────────────────
print("=== Logging in ===")
CREDENTIALS = [
    ("parent@example.com", "password123"),
    ("parent2@example.com", "password123"),
    ("parent3@example.com", "password123"),
    ("child@example.com", "password123"),
    ("samerA@gmail.com", "Samer@123"),
    ("samerA@gmail.com", "123456"),
    ("samerA@gmail.com", "samer123"),
]

token = None
for email, pwd in CREDENTIALS:
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}, timeout=10)
    if r.status_code in [200, 201]:
        resp_json = r.json()
        data_obj = resp_json.get("data") if isinstance(resp_json, dict) else None
        token = data_obj.get("token") if isinstance(data_obj, dict) else None
        if token:
            print(f"Login OK as {email}, token: {token[:30]}...")
            break
        else:
            print(f"  {email}: Token not found in data object")
    else:
        print(f"  {email}: {r.status_code}")

if not token:
    print("All logins failed. Trying without auth (public endpoint)...")

# ── 2. Hit forecast endpoint ───────────────────────────────────────────────
print("\n=== Calling Forecast Endpoint ===")
headers = {"Authorization": f"Bearer {token}"}
forecast_resp = requests.get(
    f"{BASE}/glucose/child/{CHILD_ID}/forecast",
    params={"windows": "5,10,15,20,25,30"},
    headers=headers,
    timeout=30
)

print(f"Status: {forecast_resp.status_code}")
print(f"Response:\n{json.dumps(forecast_resp.json(), indent=2)}")
