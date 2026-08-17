from celery.result import AsyncResult
from fastapi import APIRouter

from app.worker.celery_app import celery_app
from app.worker.tasks import health_check


router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("/health-check")
async def submit_health_check():
    task = health_check.delay()

    return {
        "job_id": task.id,
        "status": "queued",
    }


@router.get("/{job_id}")
async def get_job(job_id: str):
    result = AsyncResult(job_id, app=celery_app)

    response = {
        "job_id": job_id,
        "status": result.status,
    }

    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)

    return response
