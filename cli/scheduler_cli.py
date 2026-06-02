import click
import requests
import json
import os
import sys
import time

# Job output can contain arbitrary Unicode; force UTF-8 so printing logs/results
# doesn't crash on consoles with a legacy codepage (e.g. Windows cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

TERMINAL_STATES = {"SUCCESS", "FAILED", "DEAD", "CANCELED"}

API_URL = os.getenv("SCHEDULER_API_URL", "http://localhost:8000")


@click.group()
def cli():
    """Distributed Job Scheduler CLI"""
    pass


@cli.command()
@click.option("--script", "-s", required=True, type=click.Path(exists=True), help="Path to the Python script")
@click.option("--requirements", "-r", type=click.Path(exists=True), default=None, help="Path to requirements.txt")
@click.option("--image", "-i", default="python:3.11-slim", help="Base Docker image")
@click.option("--retries", default=3, type=int, help="Max retries")
@click.option("--timeout", default=300, type=int, help="Timeout in seconds")
@click.option("--env", "-e", default="{}", help="Environment variables as JSON string")
@click.option("--network/--no-network", default=False, help="Allow the job network access at runtime (default: disabled)")
def submit(script, requirements, image, retries, timeout, env, network):
    """Submit a job with a script and optional requirements."""
    files = {
        "script": ("script.py", open(script, "rb"), "text/x-python"),
    }
    if requirements:
        files["requirements"] = ("requirements.txt", open(requirements, "rb"), "text/plain")

    data = {
        "image_base": image,
        "retries": str(retries),
        "timeout": str(timeout),
        "env": env,
        "network": "true" if network else "false",
    }

    try:
        resp = requests.post(f"{API_URL}/jobs/upload", files=files, data=data)
        resp.raise_for_status()
        result = resp.json()
        click.echo(f"Job submitted: {result['job_id']}")
        click.echo(f"Status: {result['status']}")
    except requests.exceptions.ConnectionError:
        click.echo(f"Error: Cannot connect to API at {API_URL}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("job_id")
@click.option("--watch", "-w", is_flag=True, help="Poll until the job reaches a terminal state")
@click.option("--interval", default=2.0, type=float, help="Polling interval in seconds (with --watch)")
def status(job_id, watch, interval):
    """Check the status of a job."""
    try:
        while True:
            resp = requests.get(f"{API_URL}/jobs/{job_id}")
            resp.raise_for_status()
            job = resp.json()
            click.echo(json.dumps(job, indent=2))

            if not watch or job.get("status") in TERMINAL_STATES:
                break
            time.sleep(interval)
    except requests.exceptions.ConnectionError:
        click.echo(f"Error: Cannot connect to API at {API_URL}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("job_id")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def logs(job_id, follow):
    """Get logs for a job."""
    try:
        resp = requests.get(f"{API_URL}/jobs/{job_id}/logs")
        resp.raise_for_status()
        data = resp.json()

        lines = []
        if "data" in data and "result" in data.get("data", {}):
            for stream in data["data"]["result"]:
                for ts, line in stream.get("values", []):
                    lines.append(line)

        if lines:
            for line in lines:
                click.echo(line)
            return

        # Loki returned no log lines (errored or empty); the worker stores
        # job output in Postgres, so fall back to the DB result.
        resp = requests.get(f"{API_URL}/jobresult/{job_id}")
        resp.raise_for_status()
        result = resp.json()
        if result.get("result"):
            click.echo(result["result"])
        else:
            click.echo("No logs available yet.")
    except requests.exceptions.ConnectionError:
        click.echo(f"Error: Cannot connect to API at {API_URL}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("list")
@click.option("--state", "-s", default=None, help="Filter by job state")
@click.option("--limit", "-l", default=20, type=int, help="Max number of results")
def list_jobs(state, limit):
    """List recent jobs."""
    try:
        params = {"limit": limit}
        if state:
            params["state"] = state.upper()
        resp = requests.get(f"{API_URL}/jobs", params=params)
        resp.raise_for_status()
        jobs = resp.json()
        if isinstance(jobs, list):
            for job in jobs:
                click.echo(f"{job['id']}  {job['status']:<12}  {job.get('created_at', 'N/A')}")
        else:
            click.echo(json.dumps(jobs, indent=2))
    except requests.exceptions.ConnectionError:
        click.echo(f"Error: Cannot connect to API at {API_URL}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
