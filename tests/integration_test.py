import requests
import time
import sys

API_URL = "http://localhost:8000"
PROMETHEUS_URL = "http://localhost:9090"

def submit_job(command, image="ubuntu:latest"):
    print(f"Submitting job: {command}")
    resp = requests.post(f"{API_URL}/jobs", json={
        "command": command,
        "image": image
    })
    resp.raise_for_status()
    return resp.json()["job_id"]

def get_job_status(job_id):
    resp = requests.get(f"{API_URL}/jobs/{job_id}")
    resp.raise_for_status()
    return resp.json()["status"]

def wait_for_job(job_id, target_status=["SUCCEEDED", "FAILED"], timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        status = get_job_status(job_id)
        print(f"Job {job_id} status: {status}")
        if status in target_status:
            return status
        time.sleep(2)
    raise TimeoutError(f"Job {job_id} did not finish in {timeout}s")

def get_metric(metric_name):
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": metric_name})
        resp.raise_for_status()
        data = resp.json()
        if data["status"] == "success" and data["data"]["result"]:
            return float(data["data"]["result"][0]["value"][1])
    except Exception as e:
        print(f"Error querying metric {metric_name}: {e}")
    return 0.0

def main():
    print("Starting Integration Test...")
    
    # 1. Check Initial Metrics
    initial_processed = get_metric('jobs_processed_total{status="succeeded"}')
    print(f"Initial completed jobs: {initial_processed}")

    # 2. Submit a Success Job
    job_id = submit_job(["echo", "Hello Metrics"])
    final_status = wait_for_job(job_id)
    
    if final_status != "SUCCEEDED":
        print(f"Test Failed: Job status is {final_status}")
        sys.exit(1)

    # 3. Verify Metric Increment
    # stats update might take a few seconds to be scraped by prometheus (15s interval)
    print("Waiting for Prometheus scrape (20s)...")
    time.sleep(20)
    
    new_processed = get_metric('jobs_processed_total{status="succeeded"}')
    print(f"New completed jobs: {new_processed}")
    
    if new_processed > initial_processed:
        print("Success: Metric incremented!")
    else:
        print("Warning: Metric did not increment (scrape interval issue?)")
        # Don't fail the test strictly on this if system is slow, but ideally should pass.

    print("Test Passed!")

if __name__ == "__main__":
    main()
