from app.worker.celery_app import celery_app


@celery_app.task(
    name="aegis.health_check",
    bind=True,
)
def health_check(self):
    return {
        "status": "healthy",
        "worker": "aegis-celery",
    }
