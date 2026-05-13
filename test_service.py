import requests
import numpy as np
import time

def test_api():
    url = "http://127.0.0.1:8000/predict"
    
    # Generate mock data (288, 3)
    mock_data = []
    for _ in range(288):
        cgm = float(np.random.uniform(100, 200))
        bolus = float(np.random.uniform(0, 10))
        basal = float(np.random.uniform(0, 2))
        mock_data.append([cgm, bolus, basal])
        
    print(f"Sending request to {url}...")
    try:
        start_time = time.time()
        response = requests.post(url, json={"data": mock_data})
        latency = time.time() - start_time
        
        if response.status_code == 200:
            print(f"Success! (Latency: {latency:.3f}s)")
            print("Predictions:", response.json()["predictions"])
        else:
            print(f"Failed with status code {response.status_code}")
            print("Error detail:", response.text)
    except Exception as e:
        print(f"Could not connect to the server: {e}")

if __name__ == "__main__":
    test_api()
