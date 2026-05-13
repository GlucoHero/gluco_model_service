from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import numpy as np
from typing import List

from model import Crossformer

app = FastAPI(title="DCLP3 Model Service", description="Fine-tuned model for hypoglycemia detection")

MODEL_PATH = r"C:\Users\ASUS\Desktop\FINAL_MODEL_GRAD\DCLP3 FINE-TUNED ON DCLP5 DATASET\finetuned_model.pt"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Global variables to hold model and stats
model = None
base_stats = None

class PredictionRequest(BaseModel):
    # Expected shape: List of 288 items, each containing 3 floats (cgm, bolus, basal)
    data: List[List[float]]

class PredictionResponse(BaseModel):
    predictions: List[float]

@app.on_event("startup")
async def startup_event():
    global model, base_stats
    print("Loading model from:", MODEL_PATH)
    try:
        checkpoint = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)
        base_stats = checkpoint['stats']
        
        # Instantiate model with the exact parameters from training
        model = Crossformer(hl=288, ph=6, in_channels=3, d_model=64, n_heads=4, e_layers=3, dropout=0.1)
        model.load_state_dict(checkpoint['model_state_dict'])
        model = model.to(DEVICE)
        model.eval()
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")
        raise e

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
        pred = model(X_tensor)
        
    pred_np = pred.squeeze(0).cpu().numpy()
    
    # Denormalization (as per Jupyter notebook)
    # pred_mgdl = pred * stats['cgm_std'] + stats['cgm_mean']
    pred_mgdl = pred_np * base_stats['cgm_std'] + base_stats['cgm_mean']
    
    return {"predictions": pred_mgdl.tolist()}
