import io
import json
import os
from minio import Minio
from minio.error import S3Error

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minio123")
BUCKET_NAME = "jobs"

_client = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False,
        )
        if not _client.bucket_exists(BUCKET_NAME):
            _client.make_bucket(BUCKET_NAME)
    return _client


def upload_script(job_id: str, script_data: bytes):
    client = get_minio_client()
    client.put_object(
        BUCKET_NAME,
        f"{job_id}/script.py",
        io.BytesIO(script_data),
        length=len(script_data),
        content_type="text/x-python",
    )


def upload_requirements(job_id: str, requirements_data: bytes):
    client = get_minio_client()
    client.put_object(
        BUCKET_NAME,
        f"{job_id}/requirements.txt",
        io.BytesIO(requirements_data),
        length=len(requirements_data),
        content_type="text/plain",
    )


def upload_manifest(job_id: str, manifest: dict):
    client = get_minio_client()
    data = json.dumps(manifest).encode()
    client.put_object(
        BUCKET_NAME,
        f"{job_id}/manifest.json",
        io.BytesIO(data),
        length=len(data),
        content_type="application/json",
    )


def download_manifest(job_id: str) -> dict:
    client = get_minio_client()
    try:
        response = client.get_object(BUCKET_NAME, f"{job_id}/manifest.json")
        return json.loads(response.read())
    except S3Error:
        return {}
    finally:
        try:
            response.close()
            response.release_conn()
        except Exception:
            pass
