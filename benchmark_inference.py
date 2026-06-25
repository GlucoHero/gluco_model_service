import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import time
import numpy as np
import torch
from model import Crossformer

MODEL_PATH = r"C:\Users\ASUS\Desktop\FINAL_MODEL_GRAD\DCLP3 FINE-TUNED ON DCLP5 DATASET\finetuned_model.pt"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
RUNS = 100

print(f"Device: {DEVICE}")
print(f"Loading model from: {MODEL_PATH}")

checkpoint = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)
base_stats = checkpoint['stats']

model = Crossformer(hl=288, ph=6, in_channels=3, d_model=64, n_heads=4, e_layers=3, dropout=0.1)
model.load_state_dict(checkpoint['model_state_dict'])
model = model.to(DEVICE)
model.eval()
print("Model loaded.\n")

# Build a realistic dummy input (CGM ~120 mg/dL, no bolus, basal ~1 U/h)
raw = np.zeros((288, 3), dtype=np.float32)
raw[:, 0] = 120.0   # CGM
raw[:, 1] = 0.0     # bolus
raw[:, 2] = 1.0     # basal

X = raw.copy()
X[:, 0] = (X[:, 0] - base_stats['cgm_mean']) / base_stats['cgm_std']
X[:, 1] = (np.log1p(X[:, 1]) - base_stats['bolus_mean']) / base_stats['bolus_std']
X[:, 2] = (X[:, 2] - base_stats['basal_mean']) / base_stats['basal_std']
X_tensor = torch.tensor(X, dtype=torch.float32).unsqueeze(0).to(DEVICE)

# Warm-up (avoids first-run JIT / memory allocation overhead)
print("Warming up (5 runs)...")
for _ in range(5):
    with torch.no_grad():
        model(X_tensor)

# Timed runs
print(f"Benchmarking ({RUNS} runs)...")
times = []
for i in range(RUNS):
    with torch.no_grad():
        t0 = time.perf_counter()
        out = model(X_tensor)
        times.append((time.perf_counter() - t0) * 1000)

times = np.array(times)
print("\n========== INFERENCE BENCHMARK ==========")
print(f"  Runs            : {RUNS}")
print(f"  Average         : {np.mean(times):.2f} ms")
print(f"  Std deviation   : {np.std(times):.2f} ms")
print(f"  Min             : {np.min(times):.2f} ms")
print(f"  Max             : {np.max(times):.2f} ms")
print(f"  Median (p50)    : {np.percentile(times, 50):.2f} ms")
print(f"  p95             : {np.percentile(times, 95):.2f} ms")
print("=========================================")
result = "PASS" if np.mean(times) < 500 else "FAIL"
print(f"\nReal-time threshold (<500 ms): {result}")
