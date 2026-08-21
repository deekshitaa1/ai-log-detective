from fastapi import FastAPI

from app.payments import router


app = FastAPI(
    title="Payment API",
    version="1.0.0",
)

app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "payment-api",
    }
