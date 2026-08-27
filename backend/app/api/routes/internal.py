from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.core.config import settings
from app.db.models import Meeting

router = APIRouter()


def verify_service_key(x_service_key: str = Header(...)) -> None:
    """Service-to-service auth for the pipeline modules. They hold a shared key
    instead of a user JWT, so they never need direct database access."""
    if x_service_key != settings.PIPELINE_SERVICE_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service key"
        )


@router.patch(
    "/meetings/{meeting_id}/status",
    response_model=schemas.MeetingOut,
    dependencies=[Depends(verify_service_key)],
)
def update_pipeline_status(
    meeting_id: str,
    payload: schemas.PipelineStatusUpdate,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Called by the Speech-to-Text and AI Analysis modules as a meeting moves
    through the pipeline, so the dashboard reflects real progress.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    meeting.status = payload.status
    if payload.duration_seconds is not None:
        meeting.duration_seconds = payload.duration_seconds

    db.commit()
    db.refresh(meeting)
    return meeting


@router.get(
    "/meetings/{meeting_id}/file-paths",
    dependencies=[Depends(verify_service_key)],
)
def get_file_paths_for_processing(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Gives the Speech-to-Text module the stored file paths it needs to open,
    without exposing the storage layer to the frontend.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    return {
        "meeting_id": meeting.id,
        "files": [
            {
                "id": f.id,
                "file_type": f.file_type,
                "storage_backend": f.storage_backend,
                "storage_path": f.storage_path,
            }
            for f in meeting.files
        ],
    }
