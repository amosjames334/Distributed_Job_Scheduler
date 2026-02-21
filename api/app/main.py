from fastapi import FastAPI, Response
from .database import engine, Base
from api.routes.jobs import router as jobs_router
from api.routes.logs import router as logs_router
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(title="Distributed Job Scheduler API")

app.include_router(jobs_router)
app.include_router(logs_router)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
