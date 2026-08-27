import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    DateTime,
    Enum,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    meetings = relationship("Meeting", back_populates="owner", cascade="all, delete-orphan")


def generate_uuid() -> str:
    return str(uuid.uuid4())


class MeetingStatus(str, enum.Enum):
    """Where a meeting sits in the processing pipeline. The dashboard reads this
    field to show progress, and the pipeline modules advance it."""

    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    TRANSCRIBED = "transcribed"
    ANALYZED = "analyzed"
    COMPLETED = "completed"
    FAILED = "failed"


class FileType(str, enum.Enum):
    AUDIO = "audio"
    VIDEO = "video"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(String, primary_key=True, default=generate_uuid)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(MeetingStatus), default=MeetingStatus.UPLOADED, nullable=False)
    # Filled in by the Speech-to-Text module once the recording is processed.
    duration_seconds = Column(Integer, nullable=True)
    meeting_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="meetings")
    files = relationship("MeetingFile", back_populates="meeting", cascade="all, delete-orphan")
    participants = relationship("Participant", back_populates="meeting", cascade="all, delete-orphan")


class MeetingFile(Base):
    __tablename__ = "meeting_files"

    id = Column(String, primary_key=True, default=generate_uuid)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False, index=True)
    file_type = Column(Enum(FileType), nullable=False)
    original_filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    storage_backend = Column(String, nullable=False, default="local")
    content_type = Column(String, nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    checksum_sha256 = Column(String, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    meeting = relationship("Meeting", back_populates="files")


class Participant(Base):
    __tablename__ = "participants"

    id = Column(String, primary_key=True, default=generate_uuid)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    # Set later by the Speaker ID module, linking a diarised speaker to a person.
    speaker_label = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meeting = relationship("Meeting", back_populates="participants")
