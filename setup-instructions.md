# Setup Instructions

## Prerequisites
- Docker & Docker Compose
- Python 3.9+ (optional, for local development and CLI)

## Quick Start

### 1. Build and Run Infrastructure
Start the entire stack (Postgres, Redis, MinIO, Loki, API, Scheduler, Worker):
```bash
docker-compose up -d --build
```

### 2. Verify Services
- **API:** [http://localhost:8000/health](http://localhost:8000/health) (Should return `{"status": "ok"}`)
- **Prometheus:** [http://localhost:9090](http://localhost:9090)
- **Grafana:** [http://localhost:3000](http://localhost:3000) (User: `admin`, Pass: `admin`)
- **MinIO Console:** [http://localhost:9001](http://localhost:9001) (User: `minio`, Pass: `minio123`)
- **Loki:** [http://localhost:3100/ready](http://localhost:3100/ready)

### 3. Install CLI (optional)
From the project root:
```bash
pip install -e .
```
Or with Poetry:
```bash
poetry install
```

## Usage Guide

### 1. Submit a Job (New - Multipart Upload)

**Via CLI:**
```bash
# Basic submission
scheduler submit --script ./analysis.py --requirements ./requirements.txt

# With options
scheduler submit \
  --script ./train.py \
  --requirements ./requirements.txt \
  --image python:3.11-slim \
  --retries 5 \
  --timeout 600 \
  --env '{"MODEL": "gpt2", "EPOCHS": "10"}'
```

**Via curl:**
```bash
curl -X POST http://localhost:8000/jobs/upload \
  -F "script=@./my_script.py" \
  -F "requirements=@./requirements.txt" \
  -F "image_base=python:3.11-slim" \
  -F "retries=3" \
  -F "timeout=300"
```

**Via PowerShell:**
```powershell
$form = @{
    script = Get-Item ./my_script.py
    requirements = Get-Item ./requirements.txt
    image_base = "python:3.11-slim"
}
Invoke-RestMethod -Uri "http://localhost:8000/jobs/upload" -Method Post -Form $form
```

### 2. Submit a Job (Legacy - JSON)

**Via curl:**
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"command": ["echo", "Hello World"], "image": "ubuntu:latest"}'
```

### 3. Check Job Status

**Via CLI:**
```bash
scheduler status <job_id>
```

**Via curl:**
```bash
curl http://localhost:8000/jobs/<job_id>
```

### 4. View Job Logs

**Via CLI:**
```bash
scheduler logs <job_id>
```

### 5. List Jobs

**Via CLI:**
```bash
scheduler list --state failed --limit 20
```

## Job State Machine

```
PENDING
  -> ASSIGNED   (scheduler picked a worker)
      -> PULLING     (worker downloading from MinIO)
          -> INSTALLING  (pip install / image build)
              -> RUNNING    (container executing)
                  |-> SUCCESS
                  |-> FAILED
                      |-> RETRYING -> PENDING  (if retries_left > 0)
                      |-> DEAD               (retries exhausted)
```

## Docker Swarm Deployment (Testing Pending)

For production with Docker Swarm:
```bash
docker swarm init
docker stack deploy -c docker-compose.swarm.yml scheduler
```

This deploys:
- **API:** 2 replicas
- **Scheduler:** 3 replicas (HA, only leader active)
- **Worker:** Global mode (one per Swarm node)
- **MinIO, Redis, Postgres:** Pinned to manager node

## Observability

### Metrics (Prometheus)
Key metrics available at `/metrics`:
- `job_submissions_total` - Total jobs submitted
- `jobs_scheduled_total` - Jobs assigned to workers
- `jobs_processed_total{status}` - Jobs completed (succeeded/failed)
- `active_workers` - Number of healthy workers
- `cache_hits_total` / `cache_misses_total` - Environment cache performance
- `job_duration_seconds` - Job execution time histogram

### Dashboards (Grafana)
Pre-configured dashboard: "Distributed Job Scheduler - Overview"
- Job submission rate
- Active workers count
- Queue depth
- Jobs processed by status
- Cache hit/miss rate
- Job duration percentiles (p50/p95)

### Logs (Loki)
Job logs are queryable via the API:
```bash
curl http://localhost:8000/jobs/<job_id>/logs
```

## Troubleshooting

- **Port Conflicts:** Check `docker-compose ps` for port mappings
- **Container Logs:** `docker-compose logs -f api scheduler worker`
- **Database:** Ensure `DATABASE_URL` uses `postgresql+asyncpg://` for async services
- **MinIO:** Verify bucket `jobs` exists at http://localhost:9001
