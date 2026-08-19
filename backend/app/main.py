from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Meeting Intelligence System API",
    description="Backend API for AI Meeting Intelligence System",
    version="0.1.0",
)

# CORS middleware configuration placeholder
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
