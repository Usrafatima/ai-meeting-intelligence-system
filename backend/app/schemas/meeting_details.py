"""
Module 6 - Dashboard & Meeting Details
Response shapes for the meeting details page.

The brief splits that page into four sections -- Overview, Transcript, AI Insights
and Ask AI. Ask AI belongs to module 7; the other three are served by the schemas
below, one per section, so a client can fetch just the tab it is showing.

Timestamps appear twice throughout: `*_seconds` as a number for seeking the
recording, and `*_label` as the "32:45" form for display. Formatting once on the
server keeps every consumer consistent.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: Optional[str] = None
    speaker_label: Optional[str] = Field(
        None, description="Diarised speaker this person was matched to, if any"
    )


class SpeakerOut(BaseModel):
    """A voice detected in the recording, with how much of the meeting it held."""

    label: str = Field(..., description="Diarised label, e.g. 'Speaker 1'")
    participant_id: Optional[str] = None
    participant_name: Optional[str] = Field(
        None, description="Real name, once a speaker has been matched to a participant"
    )
    segment_count: int
    first_appearance: Optional[float] = Field(None, description="Seconds into the recording")
    last_appearance: Optional[float] = None
    speaking_seconds: Optional[float] = Field(
        None, description="Total time attributed to this speaker"
    )


class MediaOut(BaseModel):
    """The recording backing this meeting, and where to stream it from."""

    file_id: str
    filename: str
    file_type: str = Field(..., description="audio or video")
    content_type: Optional[str] = None
    size_bytes: int
    stream_url: str = Field(
        ..., description="Range-capable endpoint the player should use as its source"
    )


class MeetingCountsOut(BaseModel):
    """Headline numbers for the meeting, so the page can render tab badges."""

    key_points: int = 0
    decisions_total: int = 0
    decisions_pending: int = 0
    action_items_total: int = 0
    action_items_open: int = 0
    deadlines_total: int = 0
    deadlines_upcoming: int = 0
    unresolved_issues: int = 0
    participants: int = 0
    transcript_segments: int = 0


class MeetingOverviewOut(BaseModel):
    """Everything the Overview tab needs in a single request."""

    id: str
    title: str
    description: Optional[str] = None
    status: str

    meeting_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    duration_label: Optional[str] = Field(None, description="Human form, e.g. '1h 04m'")

    participants: List[ParticipantOut] = Field(default_factory=list)
    speakers: List[SpeakerOut] = Field(default_factory=list)

    summary_short: Optional[str] = None
    summary_detailed: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_notes: Optional[str] = None

    has_transcript: bool = False
    has_insights: bool = False
    counts: MeetingCountsOut = Field(default_factory=MeetingCountsOut)
    media: Optional[MediaOut] = None


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


class TranscriptSegmentOut(BaseModel):
    index: int = Field(..., description="Position in the full transcript, zero-based")
    start_time: float
    end_time: Optional[float] = None
    start_label: str = Field(..., description="Start time as mm:ss or hh:mm:ss")

    speaker: str
    speaker_id: Optional[str] = None
    speaker_name: Optional[str] = Field(
        None, description="Participant name where the speaker has been identified"
    )

    text: str
    confidence: Optional[float] = None


class MeetingTranscriptOut(BaseModel):
    """
    A page of transcript.

    When `query` is set the segments are those that matched, and `match_count`
    reports the total number of hits across the whole transcript -- not just this
    page -- so the UI can show "12 results" without fetching everything.
    """

    meeting_id: str
    language: str = "en"
    duration_seconds: Optional[float] = None
    transcriber_model: Optional[str] = None
    overall_confidence: Optional[float] = None

    total_segments: int = Field(..., description="Segments in the full transcript")
    query: Optional[str] = None
    match_count: Optional[int] = Field(
        None, description="Total matching segments; present only when a query was given"
    )

    page: int = 1
    page_size: int = 200
    segments: List[TranscriptSegmentOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# AI Insights
# ---------------------------------------------------------------------------


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task: str
    owner_name: Optional[str] = None
    participant_id: Optional[str] = None
    participant_name: Optional[str] = None

    deadline_date: Optional[date] = None
    deadline_raw: Optional[str] = Field(
        None, description="The phrase actually spoken, e.g. 'end of this month'"
    )
    is_overdue: bool = False
    days_until_due: Optional[int] = None

    status: str = "open"
    source_timestamp: Optional[float] = None
    source_timestamp_label: Optional[str] = None


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    decision: str
    timestamp_seconds: Optional[float] = None
    timestamp_label: Optional[str] = None
    status: str = "pending"


class DeadlineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    due_date: Optional[date] = None
    raw_phrase: Optional[str] = None
    source: str = "explicit"
    action_item_id: Optional[str] = None
    is_overdue: bool = False
    days_until_due: Optional[int] = None


class UnresolvedIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    issue: str
    raised_by: Optional[str] = None


class MeetingInsightsOut(BaseModel):
    """
    The AI Insights tab in one response.

    `available` is false when no analysis has been run yet. The endpoint still
    returns 200 with empty collections in that case, so a client renders an empty
    state rather than handling an error.
    """

    meeting_id: str
    available: bool = False
    generated_at: Optional[datetime] = None
    model_name: Optional[str] = None

    summary_short: Optional[str] = None
    summary_detailed: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    follow_up_items: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = None
    sentiment_notes: Optional[str] = None

    decisions: List[DecisionOut] = Field(default_factory=list)
    action_items: List[ActionItemOut] = Field(default_factory=list)
    deadlines: List[DeadlineOut] = Field(default_factory=list)
    unresolved_issues: List[UnresolvedIssueOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class GenerateInsightsRequest(BaseModel):
    summary_mode: str = Field(
        "detailed",
        pattern="^(short|detailed)$",
        description="Matches the Short / Detailed choice offered on the summary",
    )


class ActionItemStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|done)$")


class DecisionStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|confirmed)$")
