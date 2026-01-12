# Distributed Job Scheduler

A runnable, resume-ready project spec for a Python-based distributed job scheduler (mini Kubernetes-like scheduler).

## Overview

Build a Python-based distributed job scheduler that accepts jobs, schedules them on worker nodes, runs them in containers, and provides durability, HA leader election, retries, and observability. The project should be runnable locally (docker-compose) and optionally on Kubernetes.

## Tech Stack

* **Language:** Python 3.9+
* **API:** FastAPI
* **Store:** PostgreSQL, Redis Streams
* **Orchestration:** Docker Compose
* **Observability:** Prometheus, Grafana

## Features

### What Can Workers Execute?
Workers can run **any containerized workload** using Docker. This includes:

1. **Python Scripts**
   - Execute Python files from any image (e.g., `python:3.9-slim`)
   - Run data processing, ML training, web scraping, etc.
   - Example: `{"command": ["python3", "/app/script.py"], "image": "python:3.9-slim"}`

2. **Shell Commands**
   - Run bash scripts, system utilities, file operations
   - Example: `{"command": ["bash", "-c", "ls -la && echo done"], "image": "ubuntu:latest"}`

3. **Data Processing**
   - ETL pipelines, CSV/JSON processing
   - Example: `{"command": ["python3", "-c", "import pandas; print('Processing...')"], "image": "pandas-image"}`

4. **Custom Applications**
   - Any Docker image with your application
   - Example: `{"command": ["./my-app", "--config", "prod.yml"], "image": "myregistry/myapp:v1.0"}`

5. **Multi-step Workflows**
   - Chain commands using shell operators
   - Example: `{"command": ["sh", "-c", "wget data.csv && python process.py && rm data.csv"], "image": "python:3.9"}`

### Key Capabilities
- **Automatic Retries:** Failed jobs retry up to 3 times
- **Resource Isolation:** Each job runs in its own container
- **Distributed Execution:** Scale workers horizontally
- **Leader Election:** High availability with multiple schedulers
- **Observability:** Real-time metrics via Prometheus/Grafana



## Quick Start

1.  **Prerequisites:** Docker, Docker Compose, Python 3.9+
2.  **Start Infrastructure:**
    ```bash
    docker-compose up -d
    ```
3.  **Access Services:**
    *   API: http://localhost:8000
    *   Prometheus: http://localhost:9090
    *   Grafana: http://localhost:3000

## Documentation
For detailed setup instructions, usage guide, API reference, and troubleshooting, please refer to [setup-instructions.md](./setup-instructions.md).

