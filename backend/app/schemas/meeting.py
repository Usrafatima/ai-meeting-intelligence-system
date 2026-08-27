from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.db.models import MeetingStatus, FileType


class ParticipantCreate(BaseModel):
    name: str
    email: Optional[str] = None


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: Optional[str] = None
    speaker_label: Optional[str] = None


class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None
    participants: Optional[List[ParticipantCreate]] = None


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None
    status: Optional[MeetingStatus] = None
    duration_seconds: Optional[int] = None


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_type: FileType
    original_filename: str
    content_type: Optional[str] = None
    size_bytes: int
    uploaded_at: datetime


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: int
    title: str
    description: Optional[str] = None
    status: MeetingStatus
    duration_seconds: Optional[int] = None
    meeting_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    files: List[FileOut] = []
    participants: List[ParticipantOut] = []


class MeetingSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: MeetingStatus
    duration_seconds: Optional[int] = None
    meeting_date: Optional[datetime] = None
    created_at: datetime
    file_count: int = 0


class PaginatedMeetings(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[MeetingSummaryOut]


class PipelineStatusUpdate(BaseModel):
    """Body the pipeline modules send when a meeting moves to the next stage."""

    status: MeetingStatus
    duration_seconds: Optional[int] = None
