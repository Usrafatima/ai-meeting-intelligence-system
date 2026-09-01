
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
from pgvector.sqlalchemy import Vector


# =========================================================
# USER
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    hashed_password = Column(
        String,
        nullable=False,
    )

    full_name = Column(
        String(150),
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    meetings = relationship(
        "Meeting",
        back_populates="owner",
        cascade="all, delete-orphan",
    )


# =========================================================
# HELPERS
# =========================================================

def generate_uuid() -> str:
    return str(uuid.uuid4())


# =========================================================
# ENUMS
# =========================================================

class MeetingStatus(str, enum.Enum):
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


# =========================================================
# MEETING
# =========================================================

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    title = Column(
        String(255),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    # IMPORTANT:
    # Database currently stores this as VARCHAR(50),
    # so SQLAlchemy must also use String here.
    status = Column(
        String(50),
        nullable=False,
        default="uploaded",
    )

    duration_seconds = Column(
        Integer,
        nullable=True,
    )

    meeting_date = Column(
        DateTime,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    owner = relationship(
        "User",
        back_populates="meetings",
    )

    files = relationship(
        "MeetingFile",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

    participants = relationship(
        "Participant",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )


# =========================================================
# MEETING FILE
# =========================================================

class MeetingFile(Base):
    __tablename__ = "meeting_files"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )

    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id"),
        nullable=False,
        index=True,
    )

    file_type = Column(
        Enum(FileType),
        nullable=False,
    )

    original_filename = Column(
        String,
        nullable=False,
    )

    storage_path = Column(
        String,
        nullable=False,
    )

    storage_backend = Column(
        String,
        nullable=False,
        default="local",
    )

    content_type = Column(
        String,
        nullable=True,
    )

    size_bytes = Column(
        BigInteger,
        nullable=False,
    )

    checksum_sha256 = Column(
        String,
        nullable=True,
    )

    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    meeting = relationship(
        "Meeting",
        back_populates="files",
    )


# =========================================================
# PARTICIPANT
# =========================================================

class Participant(Base):
    __tablename__ = "participants"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )

    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id"),
        nullable=False,
        index=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    email = Column(
        String,
        nullable=True,
    )

    speaker_label = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    meeting = relationship(
        "Meeting",
        back_populates="participants",
    )


# =========================================================
# TRANSCRIPT CHUNK
# =========================================================

class TranscriptChunk(Base):
    """
    Stores transcript chunks used by the RAG/vector-search pipeline.
    """

    __tablename__ = "transcript_chunks"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id"),
        nullable=False,
        index=True,
    )

    content = Column(
        Text,
        nullable=False,
    )

    start_time = Column(
        String,
        nullable=True,
    )

    end_time = Column(
        String,
        nullable=True,
    )

    embedding = Column(
        Vector(768),
        nullable=True,
    )

