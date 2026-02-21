from fastapi import APIRouter, HTTPException
import uuid
import os
import httpx

router = APIRouter()

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    query = f'{{job_id="{job_id}"}}'
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{LOKI_URL}/loki/api/v1/query_range",
                params={"query": query, "limit": 1000},
                timeout=10.0,
            )
        if response.status_code == 200:
            return response.json()
        return {"error": "Loki query failed", "status": response.status_code}
    except Exception as e:
        return {"error": f"Loki unavailable: {e}", "logs": []}
