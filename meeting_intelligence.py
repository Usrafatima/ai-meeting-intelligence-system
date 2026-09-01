"""
AI Meeting Intelligence Pydantic Schemas
Request and response models for the Meeting Intelligence module.
"""
from __future__ import annotations
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TranscriptSegmentInput(BaseModel):
    """Input transcript segment — matches the shape produced by the STT module."""

    start_time: float = Field(..., description="Start time in seconds")
    end_time: Optional[float] = Field(None, description="End time in seconds")
    speaker: str = Field(..., description="Speaker label (e.g., 'Speaker 1')")
    text: str = Field(..., description="Transcribed text")


class ActionItemSchema(BaseModel):
    task: str = Field(..., description="What needs to be done")
    owner: Optional[str] = Field(None, description="Person responsible, if mentioned")
    deadline: Optional[date] = Field(None, description="Resolved calendar date, if determinable")
    deadline_raw: Optional[str] = Field(
        None, description="Original phrase used, e.g. 'next Friday', 'end of month'"
    )


class DecisionSchema(BaseModel):
    decision: str = Field(..., description="The decision that was made")
    timestamp: Optional[str] = Field(None, description="mm:ss or hh:mm:ss where it was made")


class UnresolvedIssueSchema(BaseModel):
    issue: str
    raised_by: Optional[str] = None


class AnalyzeMeetingRequest(BaseModel):
    """Request schema for the meeting intelligence analysis endpoint."""

    meeting_id: str
    transcript: List[TranscriptSegmentInput]
    summary_mode: str = Field("detailed", pattern="^(short|detailed)$")


class MeetingIntelligenceResponse(BaseModel):
    """Response schema for meeting intelligence analysis."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    summary_short: str = Field(..., description="1-3 sentence executive summary")
    summary_detailed: str = Field(..., description="Full paragraph-level summary")

    key_points: List[str] = Field(default_factory=list)
    decisions: List[DecisionSchema] = Field(default_factory=list)
    action_items: List[ActionItemSchema] = Field(default_factory=list)
    unresolved_issues: List[UnresolvedIssueSchema] = Field(default_factory=list)
    follow_up_items: List[str] = Field(default_factory=list)

    sentiment: str = Field(..., description="Overall meeting tone: positive/neutral/tense/mixed")
    sentiment_notes: Optional[str] = Field(None, description="Brief justification for the sentiment label")