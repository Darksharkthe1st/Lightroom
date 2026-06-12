from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analysis, auth, repos

app = FastAPI(
    title="Lightroom API",
    description="GitHub-powered repository analysis and resume bullet generation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.data_path.mkdir(parents=True, exist_ok=True)

app.include_router(auth.router, prefix="/api")
app.include_router(repos.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
