import docker

docker_client = docker.from_env()


def run_job(job_id: str, image: str, script_host_path: str, manifest: dict) -> tuple[int, str]:
    """Run script.py bind-mounted into the resolved image.

    Returns (exit_code, logs).
    """
    try:
        container = docker_client.containers.run(
            image=image,
            command=["python3", "/job/script.py"],
            volumes={
                script_host_path: {"bind": "/job/script.py", "mode": "ro"}
            },
            environment=manifest.get("env", {}),
            mem_limit=manifest.get("mem_limit", "512m"),
            nano_cpus=int(manifest.get("cpu_limit", 1) * 1e9),
            network_disabled=True,
            read_only=True,
            remove=True,
            name=f"job-{job_id}",
            stdout=True,
            stderr=True,
            detach=False,
        )
        logs = container.decode("utf-8") if isinstance(container, bytes) else str(container)
        return 0, logs
    except docker.errors.ContainerError as e:
        logs = e.stderr.decode("utf-8") if e.stderr else str(e)
        return e.exit_status, logs
    except Exception as e:
        return 1, str(e)
