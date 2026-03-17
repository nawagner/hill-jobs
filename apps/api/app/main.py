from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.internal_ingest import router as ingest_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.subscribe import router as subscribe_router

app = FastAPI()
app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(ingest_router)
app.include_router(subscribe_router)
