import hashlib
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile

from app.core.config import settings


class StorageBackend(ABC):
    """Storage is behind this interface so the API never cares whether a
    recording lives on local disk or in a bucket."""

    @abstractmethod
    def save(self, upload_file: UploadFile, meeting_id: str) -> Tuple[str, int, str]:
        """Persist the upload. Returns (storage_path, size_bytes, sha256_checksum)."""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        ...


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or settings.LOCAL_UPLOAD_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, upload_file: UploadFile, meeting_id: str) -> Tuple[str, int, str]:
        meeting_dir = self.base_dir / meeting_id
        meeting_dir.mkdir(parents=True, exist_ok=True)

        extension = Path(upload_file.filename or "").suffix
        stored_name = f"{uuid.uuid4()}{extension}"
        destination = meeting_dir / stored_name

        # Streamed in chunks so a long recording never has to fit in memory.
        sha256 = hashlib.sha256()
        size_bytes = 0
        with open(destination, "wb") as out_file:
            while True:
                chunk = upload_file.file.read(1024 * 1024)
                if not chunk:
                    break
                out_file.write(chunk)
                sha256.update(chunk)
                size_bytes += len(chunk)

        # Return relative path so it works regardless of where the app runs
        try:
            rel_path = destination.relative_to(self.base_dir)
        except ValueError:
            rel_path = Path(meeting_id) / stored_name
        return str(rel_path), size_bytes, sha256.hexdigest()

    def delete(self, storage_path: str) -> None:
        try:
            os.remove(storage_path)
        except FileNotFoundError:
            pass


class S3StorageBackend(StorageBackend):
    def __init__(self):
        import boto3

        self.bucket = settings.STORAGE_BUCKET
        self.client = boto3.client(
            "s3",
            region_name=settings.STORAGE_REGION or None,
            endpoint_url=settings.STORAGE_ENDPOINT or None,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY or None,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY or None,
        )

    def save(self, upload_file: UploadFile, meeting_id: str) -> Tuple[str, int, str]:
        extension = Path(upload_file.filename or "").suffix
        key = f"meetings/{meeting_id}/{uuid.uuid4()}{extension}"

        sha256 = hashlib.sha256()
        size_bytes = 0
        buffer = upload_file.file
        buffer.seek(0)
        for chunk in iter(lambda: buffer.read(1024 * 1024), b""):
            sha256.update(chunk)
            size_bytes += len(chunk)
        buffer.seek(0)

        self.client.upload_fileobj(buffer, self.bucket, key)
        return key, size_bytes, sha256.hexdigest()

    def delete(self, storage_path: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=storage_path)


def get_storage_backend() -> StorageBackend:
    if settings.STORAGE_BACKEND == "s3":
        return S3StorageBackend()
    return LocalStorageBackend()
