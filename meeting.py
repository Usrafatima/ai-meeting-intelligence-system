from typing import List

from pydantic import BaseModel, ConfigDict

from app.db.models import FileType


class ParticipantCreate(BaseModel):
    name: str
    email: str | None = None


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str | None = None
    speaker_label: str | None = None


class MeetingCreate(BaseModel):
    title: str
    participants: List[ParticipantCreate] | None = None


class MeetingUpdate(BaseModel):
    title: str | None = None


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_type: FileType
    original_filename: str
    content_type: str | None = None
    size_bytes: int
    uploaded_at: object


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    title: str
    created_at: object
    files: List[FileOut] = []
    participants: List[ParticipantOut] = []


class MeetingSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: object
    file_count: int = 0


class PaginatedMeetings(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[MeetingSummaryOut]


class PipelineStatusUpdate(BaseModel):
    pass