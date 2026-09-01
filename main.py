from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import engine, Base

# ============================================================
# IMPORTANT:
# Import ALL SQLAlchemy models BEFORE importing API routes.
# This ensures every model is registered in the same
# Base.metadata exactly once.
# ============================================================

import app.db.models  # noqa: F401
import app.db.models_stt  # noqa: F401
import app.db.models_insights  # noqa: F401

from app.api.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""

    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables checked/created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for AI Meeting Intelligence System",
    version="0.1.0",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
)


# ============================================================
# ROOT HEALTH CHECK
# ============================================================

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "service": "AI Meeting Intelligence System API",
        "version": "0.1.0",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
    }