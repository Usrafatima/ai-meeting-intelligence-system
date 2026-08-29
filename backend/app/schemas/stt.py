"""
Speech-to-Text Pydantic Schemas
Request and response models for the STT module.
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TranscriptSegmentSchema(BaseModel):
    """Schema for a single transcript segment with speaker info."""

    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    speaker: str = Field(..., description="Speaker label (e.g., 'Speaker 1')")
    text: str = Field(..., description="Transcribed text")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    speaker_id: Optional[str] = Field(None, description="Mapped participant ID")


class SpeakerMappingSchema(BaseModel):
    """Schema for speaker-to-participant mapping."""

    diarizer_speaker: str = Field(..., description="Diarized speaker label")
    participant_id: Optional[str] = Field(None, description="Matched participant ID")
    participant_name: Optional[str] = Field(None, description="Participant name")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class STTProcessingResponse(BaseModel):
    """Response schema for STT processing endpoint."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    status: str = Field(..., description="Processing status (success/failed)")
    raw_text: str = Field(..., description="Raw transcription without speaker labels")
    formatted_text: str = Field(..., description="Text with speaker labels")
    segments: List[TranscriptSegmentSchema] = Field(default_factory=list)
    speaker_mappings: List[SpeakerMappingSchema] = Field(default_factory=list)
    processing_time_seconds: int = Field(0, description="Processing duration in seconds")
    transcriber_model: str = Field(default="unknown", description="Model used for transcription")


class TranscriptResponse(BaseModel):
    """Response schema for transcript retrieval."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    raw_text: str = ""
    formatted_text: str = ""
    language: str = "en"
    segments: List[TranscriptSegmentSchema] = Field(default_factory=list)
    overall_confidence: Optional[float] = None
    duration_seconds: Optional[int] = None
    transcriber_model: Optional[str] = None
    created_at: Optional[datetime] = None


class SpeakerMappingUpdate(BaseModel):
    """Schema for updating speaker-to-participant mappings."""

    mappings: List[SpeakerMappingUpdateItem]


class SpeakerMappingUpdateItem(BaseModel):
    """Single speaker mapping update."""

    participant_id: str
    speaker_label: str


class SpeakerMappingUpdateResponse(BaseModel):
    """Response for speaker mapping update."""

    meeting_id: str
    status: str
    mappings_updated: int