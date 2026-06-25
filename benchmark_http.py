"""
HTTP round-trip benchmark for the GlucoHero model service.
Measures the full pipeline: HTTP request -> validation -> normalization -> inference -> response.
This is the actual latency NestJS waits on when requesting a forecast.
"""
import time
import numpy as np
import requests

URL = "http://127.0.0.1:8001/predict"
RUNS = 100
WARMUP = 5

# Representative input: 288 timesteps x 3 channels (CGM ~120 mg/dL, no bolus, 1 U/h basal)
sample_input = {"data": [[120.0, 0.0, 1.0]] * 288}

# Wait for server to be ready
print("Waiting for model service to be ready...")
for attempt in range(30):
    try:
        r = requests.get("http://127.0.0.1:8001/docs", timeout=2)
        if r.status_code == 200:
            print("Server is ready.\n")
            break
    except Exception:
        time.sleep(1)
else:
    print("ERROR: Server did not start in time.")
    exit(1)

# Warm-up
print(f"Warming up ({WARMUP} requests)...")
for _ in range(WARMUP):
    requests.post(URL, json=sample_input)

# Timed runs
print(f"Benchmarking ({RUNS} requests)...\n")
times = []
for i in range(RUNS):
    t0 = time.perf_counter()
    resp = requests.post(URL, json=sample_input)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    times.append(elapsed_ms)
    if resp.status_code != 200:
        print(f"  Run {i+1}: ERROR {resp.status_code}")

times = np.array(times)

print("========== HTTP ROUND-TRIP BENCHMARK (model service) ==========")
print(f"  Endpoint        : POST {URL}")
print(f"  Input shape     : (288, 3) — 24h CGM + bolus + basal")
print(f"  Runs            : {RUNS}  (after {WARMUP} warm-up)")
print(f"  Average         : {np.mean(times):.2f} ms")
print(f"  Std deviation   : {np.std(times):.2f} ms")
print(f"  Min             : {np.min(times):.2f} ms")
print(f"  Max             : {np.max(times):.2f} ms")
print(f"  Median (p50)    : {np.percentile(times, 50):.2f} ms")
print(f"  p95             : {np.percentile(times, 95):.2f} ms")
print("===============================================================")
result = "PASS" if np.mean(times) < 500 else "FAIL"
print(f"\nReal-time threshold (<500 ms): {result}")
