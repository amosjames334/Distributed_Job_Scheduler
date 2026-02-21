import click
import requests
import json
import os
import sys

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
def submit(script, requirements, image, retries, timeout, env):
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
def status(job_id):
    """Check the status of a job."""
    try:
        resp = requests.get(f"{API_URL}/jobs/{job_id}")
        resp.raise_for_status()
        job = resp.json()
        click.echo(json.dumps(job, indent=2))
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

        if "error" in data and data.get("logs") == []:
            click.echo(f"Loki unavailable, fetching result from DB...")
            resp = requests.get(f"{API_URL}/jobresult/{job_id}")
            resp.raise_for_status()
            result = resp.json()
            if result.get("result"):
                click.echo(result["result"])
            else:
                click.echo("No logs available yet.")
            return

        if "data" in data and "result" in data["data"]:
            for stream in data["data"]["result"]:
                for ts, line in stream.get("values", []):
                    click.echo(line)
        else:
            click.echo(json.dumps(data, indent=2))
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
