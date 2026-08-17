from fastapi import FastAPI

from app.api.routes.jobs import router as jobs_router
from app.api.routes.incidents import router as incidents_router
from app.api.routes.projects import router as projects_router
from app.api.routes.logs import router as logs_router
from app.api.routes.detections import router as detections_router


app = FastAPI(
    title="AegisAI",
    version="0.1.0",
)


app.include_router(jobs_router)
app.include_router(incidents_router)
app.include_router(projects_router)
app.include_router(logs_router)
app.include_router(detections_router)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "api",
    }
