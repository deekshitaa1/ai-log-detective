from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.incidents import router as incidents_router
from app.api.routes.logs import router as logs_router
from app.api.routes.projects import router as projects_router
from app.api.routes.repositories import router as repositories_router


app = FastAPI(
    title="AegisAI Reliability Engine",
    version="0.1.0",
)


# ---------------------------------------------------------
# Frontend CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# API routes
# ---------------------------------------------------------

app.include_router(projects_router)
app.include_router(repositories_router)
app.include_router(incidents_router)
app.include_router(logs_router)


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "aegis-ai-api",
    }
