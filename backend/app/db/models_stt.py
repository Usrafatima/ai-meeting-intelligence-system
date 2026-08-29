"""
Speech-to-Text Database Models
This module contains models specific to the speech-to-text functionality.
These can be integrated into the main models.py or used standalone.
"""
import enum
import uuid
from typing import List, Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class TranscriptFormat(str, enum.Enum):
    """Format of the stored transcript."""
    RAW = "raw"
    FORMATTED = "formatted"
    JSON = "json"


class SpeakerLabel(str, enum.Enum):
    """Speaker identification confidence level."""
    CONFIDENT = "confident"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"


class MeetingTranscript(Base):
    """
    Stores the transcript data for a meeting.
    One-to-one relationship with Meeting.
    """
    __tablename__ = "meeting_transcripts"

    id = Column(String, primary_key=True, default=generate_uuid)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False, index=True, unique=True)

    # Raw text transcription (no speaker labels)
    raw_text = Column(Text, nullable=True)

    # Formatted text with speaker labels
    formatted_text = Column(Text, nullable=True)

    # JSON representation of segments
    segments_json = Column(Text, nullable=True)  # Can store as JSON string

    # Detection metadata
    language = Column(String, default="en", nullable=False)
    duration_seconds = Column(Float, nullable=True)

    # Confidence scores
    overall_confidence = Column(Float, nullable=True)
    transcriber_model = Column(String, default="unknown", nullable=False)

    # Processing metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting = relationship("Meeting", backref="transcript")


class TranscriptSegment(Base):
    """
    Individual segments of transcript with speaker information.
    One-to-many relationship with MeetingTranscript.
    """
    __tablename__ = "transcript_segments"

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("meeting_transcripts.id"), nullable=False, index=True)

    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)

    speaker_label = Column(String, nullable=True)  # e.g., "Speaker 1", "Speaker 2"
    speaker_confidence = Column(Float, nullable=True)
    speaker_id = Column(String, nullable=True)  # Maps to Participant.id

    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)

    # Keywords and topics extracted from this segment
    keywords_json = Column(String, nullable=True)  # JSON string

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transcript = relationship("MeetingTranscript", backref="segments")


class SpeakerDiarization(Base):
    """
    Speaker diarization results and mappings.
    Links diarized speaker segments to actual meeting participants.
    """
    __tablename__ = "speaker_diarizations"

    id = Column(String, primary_key=True, default=generate_uuid)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False, index=True)

    # Speaker identification
    diarizer_speaker = Column(String, nullable=False)  # "Speaker 1", "Speaker 2", etc.
    participant_id = Column(String, ForeignKey("participants.id"), nullable=True)

    # Confidence in the mapping
    confidence = Column(Float, nullable=True)

    # Timestamps of when this speaker appeared
    first_appearance = Column(Float, nullable=True)
    last_appearance = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meeting = relationship("Meeting", backref="speaker_diarizations")
    participant = relationship("Participant", backref="speaker_mappings")