# DCLP3 Model Service

This is an independent FastAPI web service that loads the fine-tuned DCLP3 PyTorch model and serves predictions for hypoglycemia detection.

## Prerequisites

1. Ensure you have Python installed.
2. Activate the virtual environment:
```powershell
.\env\Scripts\Activate.ps1
```
*(If you are using Command Prompt instead of PowerShell, run `.\env\Scripts\activate.bat` instead).*

3. Install the necessary dependencies:

```powershell
pip install -r requirements.txt
```

## How to Run the Service

To start the server, open PowerShell or Command Prompt, navigate to this directory, and run:

```powershell
uvicorn main:app --host 0.0.0.0 --port 8001
```

*(Optional)* Add `--reload` if you are modifying the code and want it to auto-reload:
```powershell
uvicorn main:app --reload --port 8001
```

## How to Kill an Old Running Instance

If you try to start the server and encounter an error like `error while attempting to bind on address ('0.0.0.0', 8001)`, it means an older instance of the server is still running in the background.

You can forcefully kill the old process blocking port 8001 using Windows PowerShell:

**Option 1 (One-liner in PowerShell):**
```powershell
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8001).OwningProcess -Force
```

**Option 2 (Find and kill manually):**
1. Find the Process ID (PID) using the port:
```cmd
netstat -ano | findstr :8001
```
2. Look at the last number on the line (e.g., `12345`), and kill it by running:
```cmd
taskkill /PID 12345 /F
```

## How to Use the API

Send a `POST` request to `http://127.0.0.1:8001/predict`.

The API expects a JSON payload containing an array of exactly 288 records, each with 3 variables: `[cgm, bolus, basal]`.

**Example Request Payload:**
```json
{
  "data": [
    [120.5, 2.0, 0.5],
    [121.0, 0.0, 0.5]
  ]
}
``` *(Note: Must contain 288 items total)*

**Example Response:**
```json
{
  "predictions": [118.2, 115.5, 112.0, 108.4, 105.1, 101.9]
}
```
