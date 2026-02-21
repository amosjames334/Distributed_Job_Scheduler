import hashlib
import io
import os
import docker

docker_client = docker.from_env()


def pull_bundle(minio_client, job_id: str, tmp_dir: str):
    """Download script + requirements from MinIO to local /tmp."""
    os.makedirs(tmp_dir, exist_ok=True)
    minio_client.fget_object("jobs", f"{job_id}/script.py", f"{tmp_dir}/script.py")
    try:
        minio_client.fget_object(
            "jobs", f"{job_id}/requirements.txt", f"{tmp_dir}/requirements.txt"
        )
    except Exception:
        with open(f"{tmp_dir}/requirements.txt", "w") as f:
            f.write("")


def compute_cache_key(base_image: str, req_path: str) -> str:
    """Hash requirements.txt to produce a stable, unique image tag."""
    content = open(req_path, "rb").read()
    req_hash = hashlib.sha256(content).hexdigest()[:12]
    safe_base = base_image.replace(":", "-").replace("/", "-")
    return f"{safe_base}-{req_hash}"


def resolve_image(base_image: str, req_path: str) -> tuple[str, bool]:
    """Return a Docker image tag with all dependencies installed.

    Returns (image_tag, cache_hit).
    """
    reqs = open(req_path).read().strip()
    if not reqs:
        return base_image, True

    cache_key = compute_cache_key(base_image, req_path)

    try:
        docker_client.images.get(cache_key)
        return cache_key, True
    except docker.errors.ImageNotFound:
        pass

    packages = " ".join(reqs.splitlines())
    dockerfile = f"""\
FROM {base_image}
RUN pip install --no-cache-dir {packages}
""".encode()

    docker_client.images.build(
        fileobj=io.BytesIO(dockerfile),
        tag=cache_key,
        rm=True,
    )
    return cache_key, False
