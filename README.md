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

