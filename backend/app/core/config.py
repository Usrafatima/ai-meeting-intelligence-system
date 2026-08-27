import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Meeting Intelligence System API"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname")

    # Storage for meeting audio/video uploads (module 3).
    # STORAGE_BACKEND switches between local disk and any S3-compatible bucket
    # (AWS S3, MinIO) without touching application code.
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    LOCAL_UPLOAD_DIR: str = "./uploads"
    STORAGE_BUCKET: str = ""
    STORAGE_REGION: str = ""
    STORAGE_ENDPOINT: str = ""
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 1024

    # Shared key the pipeline modules (Speech-to-Text, Speaker ID, AI Analysis)
    # send as x-service-key when calling the internal endpoints.
    PIPELINE_SERVICE_KEY: str = "change-me-in-env"

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )

settings = Settings()

# Accepted upload formats, kept here so the API and the storage layer agree.
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
ALLOWED_EXTENSIONS = ALLOWED_AUDIO_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS
