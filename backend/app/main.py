from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.api import api_router
from app.db.database import engine, Base
import app.db.models  # noqa
import app.db.models_stt  # noqa - STT models for transcript/speaker diarization

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Error creating tables: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for AI Meeting Intelligence System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def read_root():
    """Root health check endpoint to confirm backend service is running."""
    return {
        "status": "healthy",
        "service": "AI Meeting Intelligence System API",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    """Service health check endpoint."""
    return {"status": "ok"}
