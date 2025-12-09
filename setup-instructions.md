# Setup Instructions

## Prerequisites
- Docker & Docker Compose
- Python 3.9+ (optional, for local development outside Docker)

## Phase 0: Scaffolding (Completed)

### 1. Build and Run Infrastructure
Start the entire stack (Postgres, Redis, Etcd, MinIO, API, Scheduler, Worker):
```bash
docker-compose up -d --build
```
> **Note:** The `--build` flag is crucial to ensure the latest Dockerfiles and dependencies are used.

### 2. Verify Services
- **API:** [http://localhost:8000/health](http://localhost:8000/health) (Should return `{"status": "ok"}`)
- **Prometheus:** [http://localhost:9090](http://localhost:9090)
- **Grafana:** [http://localhost:3000](http://localhost:3000) (User: `admin`, Pass: `admin`) - *Check "Distributed Job Scheduler - Overview" dashboard*
- **MinIO Console:** [http://localhost:9001](http://localhost:9001) (User: `minio`, Pass: `minio123`)

### 3. Phase 1 Verification (MVP)
1.  **Submit a Job:**
    ```bash
    curl -X POST http://localhost:8000/jobs \
      -H "Content-Type: application/json" \
      -d '{"command": ["echo", "Hello World"], "image": "ubuntu:latest"}'
    ```
    Should return `{"job_id": "...", "status": "PENDING"}`.
    
    ```powershell
    Invoke-WebRequest -Uri "http://localhost:8000/jobs" `
    -Method Post `
    -Headers @{ "Content-Type" = "application/json" } `
    -Body '{"command": ["echo", "Hello World"], "image": "ubuntu:latest"}'
    ```

2.  **Check Status:**
    To see if the worker picked it up (status should go to RUNNING -> SUCCEEDED):
    ```bash
    curl http://localhost:8000/jobs/<job_id>
    ```

3.  **Troubleshooting**
    - **Port Conflicts:** If `2379` is in use, Etcd is mapped to `2389` on host. Use `docker-compose ps` to see ports.
    - **Container Logs:** If a service fails, check logs:
      ```bash
      docker logs distributed_job_scheduler-api-1
      docker logs distributed_job_scheduler-worker-1
      ```
    - **Database Connection:** Ensure `DATABASE_URL` uses `postgresql+asyncpg://` for async services.

    ### Phase 2: Verify Logs
    ```bash
    docker-compose logs -f scheduler worker
    ```

    ### Phase 3: Verify Leader Election
    1.  **Scale Up:**
        ```bash
        docker-compose up -d --scale scheduler=2
        ```
    2.  **Check Leadership:**
        ```bash
        docker-compose logs -f scheduler
        ```
        One instance should say `I am the LEADER`, the other `I am a FOLLOWER`.

    ### Phase 4: Verify Reliability
    1.  **Submit Failing Job:**
        ```bash
        curl -X POST http://localhost:8000/jobs \
          -H "Content-Type: application/json" \
          -d '{"command": ["ls", "/nonexistent"], "image": "ubuntu:latest"}'
        ```
    2.  **Watch Retries:**
        The job status will cycle `FAILED` -> `PENDING` -> `RUNNING` -> `FAILED` until `max_retries` (3) is reached.
        ```bash
        curl http://localhost:8000/jobs/<job_id>
        ```

## Usage Guide

### 1. Job Submission
**Endpoint:** `POST /jobs`
**Description:** Submits a new job to the distributed system.
**Format (JSON):**
```json
{
  "command": ["executable", "arg1", "arg2"],  // Required: List of strings
  "image": "image:tag",                       // Optional: Docker image (default: ubuntu:latest)
  "resources": {"cpu": 0.5, "mem_mb": 128}    // Optional: Resource limits
}
```

**Examples:**

*   **Bash (curl):**
    ```bash
    curl -X POST http://localhost:8000/jobs \
      -H "Content-Type: application/json" \
      -d '{"command": ["echo", "Hello Distributed World"], "image": "alpine:latest"}'
    ```

*   **PowerShell:**
    ```powershell
    Invoke-WebRequest -Uri "http://localhost:8000/jobs" `
      -Method Post `
      -Headers @{ "Content-Type" = "application/json" } `
      -Body '{"command": ["python3", "-c", "print(1+1)"], "image": "python:3.9-slim"}'
    ```

### 2. Job Status
**Endpoint:** `GET /jobs/{job_id}`
**Description:** Check the current status of a job.
**Response:**
```json
{
  "id": "uuid",
  "status": "PENDING | QUEUED | RUNNING | SUCCEEDED | FAILED",
  "result": "...", (if applicable)
  "retry_count": 0
}
```

### 3. Observability
**Endpoint:** `GET /metrics`
**Description:** Prometheus metrics for system monitoring.
**Key Metrics:**
- `job_submissions_total`: Total jobs received by API.
- `jobs_scheduled_total`: Jobs assigned to workers.
- `jobs_processed_total`: Jobs completed by workers (status=`succeeded`/`failed`).
- `active_workers`: Number of healthy workers connected.

