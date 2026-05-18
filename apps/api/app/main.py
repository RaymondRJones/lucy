from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    create_db_and_tables()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    description="Lucy API for a local, marriage-based I-485 packet workspace.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}
