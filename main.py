from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import numpy as np
import time
from typing import List

from model import Crossformer

MODEL_PATH = r"C:\Users\ASUS\Desktop\FINAL_MODEL_GRAD\DCLP3 FINE-TUNED ON DCLP5 DATASET\finetuned_model.pt"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model = None
base_stats = None

class PredictionRequest(BaseModel):
    # Expected shape: List of 288 items, each containing 3 floats (cgm, bolus, basal)
    data: List[List[float]]

class PredictionResponse(BaseModel):
    predictions: List[float]
    inference_time_ms: float

class BenchmarkResponse(BaseModel):
    runs: int
    average_inference_time_ms: float
    std_inference_time_ms: float
    min_ms: float
    max_ms: float

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, base_stats
    print("Loading model from:", MODEL_PATH)
    try:
        checkpoint = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)
        base_stats = checkpoint['stats']
        model = Crossformer(hl=288, ph=6, in_channels=3, d_model=64, n_heads=4, e_layers=3, dropout=0.1)
        model.load_state_dict(checkpoint['model_state_dict'])
        model = model.to(DEVICE)
        model.eval()
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")
        raise e
    yield  # app runs here

app = FastAPI(
    title="DCLP3 Model Service",
    description="Fine-tuned model for hypoglycemia detection",
    lifespan=lifespan,
)

@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    if model is None or base_stats is None:
        raise HTTPException(status_code=500, detail="Model is not loaded.")
    
    # Input shape validation
    data = np.array(request.data, dtype=np.float32)
    if data.shape != (288, 3):
        raise HTTPException(status_code=400, detail=f"Expected input shape (288, 3), but got {data.shape}")
    
    # Normalization (as per Jupyter notebook logic)
    # X[:, 0] = (X[:, 0] - self.stats['cgm_mean']) / self.stats['cgm_std']
    # X[:, 1] = (np.log1p(X[:, 1]) - self.stats['bolus_mean']) / self.stats['bolus_std']
    # X[:, 2] = (X[:, 2] - self.stats['basal_mean']) / self.stats['basal_std']
    
    X = data.copy()
    X[:, 0] = (X[:, 0] - base_stats['cgm_mean']) / base_stats['cgm_std']
    X[:, 1] = (np.log1p(X[:, 1]) - base_stats['bolus_mean']) / base_stats['bolus_std']
    X[:, 2] = (X[:, 2] - base_stats['basal_mean']) / base_stats['basal_std']
    
    # Add batch dimension
    X_tensor = torch.tensor(X, dtype=torch.float32).unsqueeze(0).to(DEVICE)
    
    with torch.no_grad():
        t_start = time.perf_counter()
        pred = model(X_tensor)
        inference_time_ms = (time.perf_counter() - t_start) * 1000

    pred_np = pred.squeeze(0).cpu().numpy()

    # Denormalization (as per Jupyter notebook)
    # pred_mgdl = pred * stats['cgm_std'] + stats['cgm_mean']
    pred_mgdl = pred_np * base_stats['cgm_std'] + base_stats['cgm_mean']

    print(f"Inference time: {inference_time_ms:.2f} ms")
    return {"predictions": pred_mgdl.tolist(), "inference_time_ms": round(inference_time_ms, 3)}


@app.post("/benchmark", response_model=BenchmarkResponse)
async def benchmark(request: PredictionRequest):
    """Run 100 inference passes on the supplied input and report timing statistics."""
    if model is None or base_stats is None:
        raise HTTPException(status_code=500, detail="Model is not loaded.")

    data = np.array(request.data, dtype=np.float32)
    if data.shape != (288, 3):
        raise HTTPException(status_code=400, detail=f"Expected input shape (288, 3), but got {data.shape}")

    X = data.copy()
    X[:, 0] = (X[:, 0] - base_stats['cgm_mean']) / base_stats['cgm_std']
    X[:, 1] = (np.log1p(X[:, 1]) - base_stats['bolus_mean']) / base_stats['bolus_std']
    X[:, 2] = (X[:, 2] - base_stats['basal_mean']) / base_stats['basal_std']
    X_tensor = torch.tensor(X, dtype=torch.float32).unsqueeze(0).to(DEVICE)

    times = []
    for _ in range(100):
        with torch.no_grad():
            t0 = time.perf_counter()
            model(X_tensor)
            times.append((time.perf_counter() - t0) * 1000)

    avg_ms = float(np.mean(times))
    std_ms = float(np.std(times))
    print(f"Benchmark (100 runs) — avg: {avg_ms:.2f} ms  std: {std_ms:.2f} ms")

    return {
        "runs": 100,
        "average_inference_time_ms": round(avg_ms, 2),
        "std_inference_time_ms": round(std_ms, 2),
        "min_ms": round(float(np.min(times)), 2),
        "max_ms": round(float(np.max(times)), 2),
    }
