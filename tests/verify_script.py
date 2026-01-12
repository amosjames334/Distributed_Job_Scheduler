import requests
import time
import sys

API_URL = "http://localhost:8000"

def submit_script_job():
    script = """
import torch
import torch.nn as nn
import torch.optim as optim

# 1. Create training data
x = torch.tensor([[1.0], [2.0], [3.0], [4.0]])
y = torch.tensor([[3.0], [5.0], [7.0], [9.0]])  # y = 2x + 1

# 2. Define a simple model
model = nn.Linear(1, 1)

# 3. Loss function and optimizer
criterion = nn.MSELoss()
optimizer = optim.SGD(model.parameters(), lr=0.01)

# 4. Training loop
for epoch in range(1000):
    optimizer.zero_grad()      # clear gradients
    outputs = model(x)         # forward pass
    loss = criterion(outputs, y)
    loss.backward()            # backpropagation
    optimizer.step()           # update weights

# 5. Test the model
test_x = torch.tensor([[5.0]])
prediction = model(test_x)

print("Prediction for x=5:", prediction.item())


"""
    print(f"Submitting script job...")
    resp = requests.post(f"{API_URL}/jobs", json={
        "script": script,
        "image": "amancevice/pandas:slim"
    })
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    print(f"Job ID: {job_id}")
    return job_id

def get_job_result(job_id):
    resp = requests.get(f"{API_URL}/jobresult/{job_id}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()

def wait_for_job(job_id, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        result_data = get_job_result(job_id)
        if result_data:
            status = result_data["status"]
            print(f"Job Status: {status}")
            if status in ["SUCCEEDED", "FAILED"]:
                return result_data
        time.sleep(2)
    raise TimeoutError(f"Job {job_id} did not finish in {timeout}s")

def main():
    try:
        job_id = submit_script_job()
        result = wait_for_job(job_id)
        
        print("\nJob Finished!")
        print("Status:", result["status"])
        print("Output:\n", result["result"])
        
        if "Average Age:" in result["result"]:
            print("\nSUCCESS: Output matches expected string.")
        else:
            print("\nFAILURE: Output does not match.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Test Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
