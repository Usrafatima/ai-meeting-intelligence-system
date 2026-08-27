from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.core.config import (
    settings,
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_EXTENSIONS,
)
from app.db.models import Meeting, MeetingFile, Participant, MeetingStatus, FileType, User
from app.services.storage import get_storage_backend

router = APIRouter()


def _get_owned_meeting(db: Session, meeting_id: str, user_id: int) -> Meeting:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if meeting.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your meeting")
    return meeting


@router.post("", response_model=schemas.MeetingOut, status_code=status.HTTP_201_CREATED)
def create_meeting(
    payload: schemas.MeetingCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a meeting record, optionally with its participants.
    """
    meeting = Meeting(
        owner_id=current_user.id,
        title=payload.title,
        description=payload.description,
        meeting_date=payload.meeting_date,
        status=MeetingStatus.UPLOADED,
    )
    db.add(meeting)
    db.flush()

    for participant in payload.participants or []:
        db.add(Participant(meeting_id=meeting.id, name=participant.name, email=participant.email))

    db.commit()
    db.refresh(meeting)
    return meeting


@router.get("", response_model=schemas.PaginatedMeetings)
def list_meetings(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    search: Optional[str] = Query(None, description="Search meeting title and description"),
    meeting_status: Optional[MeetingStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Any:
    """
    List the current user's meetings, with search, status filter and pagination.
    """
    query = db.query(Meeting).filter(Meeting.owner_id == current_user.id)

    if search:
        query = query.filter(
            or_(Meeting.title.ilike(f"%{search}%"), Meeting.description.ilike(f"%{search}%"))
        )

    if meeting_status:
        query = query.filter(Meeting.status == meeting_status)

    total = query.count()
    meetings = (
        query.order_by(Meeting.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        schemas.MeetingSummaryOut(
            id=m.id,
            title=m.title,
            status=m.status,
            duration_seconds=m.duration_seconds,
            meeting_date=m.meeting_date,
            created_at=m.created_at,
            file_count=len(m.files),
        )
        for m in meetings
    ]

    return schemas.PaginatedMeetings(total=total, page=page, page_size=page_size, items=items)


@router.get("/{meeting_id}", response_model=schemas.MeetingOut)
def get_meeting(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get one meeting in full, including its files and participants.
    """
    return _get_owned_meeting(db, meeting_id, current_user.id)


@router.patch("/{meeting_id}", response_model=schemas.MeetingOut)
def update_meeting(
    meeting_id: str,
    payload: schemas.MeetingUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update a meeting's title, description, date or status.
    """
    meeting = _get_owned_meeting(db, meeting_id, current_user.id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(meeting, field, value)

    db.commit()
    db.refresh(meeting)
    return meeting


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> None:
    """
    Delete a meeting along with every file stored against it.
    """
    meeting = _get_owned_meeting(db, meeting_id, current_user.id)

    storage = get_storage_backend()
    for meeting_file in meeting.files:
        storage.delete(meeting_file.storage_path)

    db.delete(meeting)
    db.commit()
    return None


@router.post(
    "/{meeting_id}/files",
    response_model=schemas.FileOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_meeting_file(
    meeting_id: str,
    upload_file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Upload an audio or video recording against a meeting and queue it for the
    Speech-to-Text module.
    """
    meeting = _get_owned_meeting(db, meeting_id, current_user.id)

    extension = Path(upload_file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type {extension}. Allowed types: {sorted(ALLOWED_EXTENSIONS)}",
        )

    file_type = FileType.AUDIO if extension in ALLOWED_AUDIO_EXTENSIONS else FileType.VIDEO

    storage = get_storage_backend()
    storage_path, size_bytes, checksum = storage.save(upload_file, meeting_id)

    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        storage.delete(storage_path)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    meeting_file = MeetingFile(
        meeting_id=meeting.id,
        file_type=file_type,
        original_filename=upload_file.filename or "unknown",
        storage_path=storage_path,
        storage_backend=settings.STORAGE_BACKEND,
        content_type=upload_file.content_type,
        size_bytes=size_bytes,
        checksum_sha256=checksum,
    )
    db.add(meeting_file)

    meeting.status = MeetingStatus.QUEUED
    db.commit()
    db.refresh(meeting_file)

    return meeting_file


@router.get("/{meeting_id}/files", response_model=List[schemas.FileOut])
def list_meeting_files(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    List the files attached to a meeting.
    """
    meeting = _get_owned_meeting(db, meeting_id, current_user.id)
    return meeting.files


@router.delete("/{meeting_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting_file(
    meeting_id: str,
    file_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> None:
    """
    Remove one file from a meeting and delete it from storage.
    """
    meeting = _get_owned_meeting(db, meeting_id, current_user.id)
    meeting_file = next((f for f in meeting.files if f.id == file_id), None)
    if not meeting_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    storage = get_storage_backend()
    storage.delete(meeting_file.storage_path)

    db.delete(meeting_file)
    db.commit()
    return None
