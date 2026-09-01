"""
Module 6 - Dashboard & Meeting Details
Response shapes for the dashboard.

The brief asks the dashboard to show recent meetings, processing status, meeting
duration, number of action items, pending decisions, upcoming deadlines, and to
let the user search their meetings. Those are aggregates over every meeting a
user owns, so each is served pre-computed rather than assembled by the client
from a list of meetings.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class MeetingStatsOut(BaseModel):
    total: int = 0
    processing: int = Field(0, description="Queued, uploaded or actively processing")
    completed: int = Field(0, description="Transcribed, analysed or completed")
    failed: int = 0
    by_status: Dict[str, int] = Field(
        default_factory=dict, description="Exact count per pipeline status"
    )


class ActionItemStatsOut(BaseModel):
    total: int = 0
    open: int = 0
    done: int = 0
    overdue: int = Field(0, description="Open, with a due date already past")


class DecisionStatsOut(BaseModel):
    total: int = 0
    pending: int = 0
    confirmed: int = 0


class DeadlineStatsOut(BaseModel):
    total: int = Field(0, description="Deadlines with a resolved calendar date")
    overdue: int = 0
    due_today: int = 0
    upcoming: int = Field(0, description="Due within the requested horizon")
    unscheduled: int = Field(
        0, description="Mentioned as a phrase but never resolvable to a date"
    )


class DashboardStatsOut(BaseModel):
    """Every headline number the dashboard shows, in one request."""

    meetings: MeetingStatsOut
    action_items: ActionItemStatsOut
    decisions: DecisionStatsOut
    deadlines: DeadlineStatsOut

    unresolved_issues: int = 0
    awaiting_analysis: int = Field(
        0, description="Meetings with a transcript stored but no insights generated"
    )

    total_duration_seconds: int = 0
    total_duration_label: str = "0s"
    horizon_days: int = Field(7, description="Window used for the upcoming deadline count")


# ---------------------------------------------------------------------------
# Recent meetings
# ---------------------------------------------------------------------------


class RecentMeetingOut(BaseModel):
    """A meeting card on the dashboard, with its own counts already resolved."""

    id: str
    title: str
    status: str
    meeting_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    duration_seconds: Optional[int] = None
    duration_label: Optional[str] = None

    participant_count: int = 0
    file_count: int = 0
    has_transcript: bool = False
    has_insights: bool = False

    action_items_total: int = 0
    action_items_open: int = 0
    decisions_pending: int = 0
    next_deadline: Optional[date] = None

    summary_short: Optional[str] = None
    sentiment: Optional[str] = None


class RecentMeetingsOut(BaseModel):
    total: int
    items: List[RecentMeetingOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Deadlines and decisions
# ---------------------------------------------------------------------------


class UpcomingDeadlineOut(BaseModel):
    id: str
    title: str
    due_date: Optional[date] = None
    raw_phrase: Optional[str] = None
    source: str = "explicit"

    meeting_id: str
    meeting_title: str

    action_item_id: Optional[str] = None
    owner_name: Optional[str] = None
    action_item_status: Optional[str] = None

    days_until_due: Optional[int] = None
    is_overdue: bool = False


class UpcomingDeadlinesOut(BaseModel):
    total: int
    horizon_days: int
    include_overdue: bool
    items: List[UpcomingDeadlineOut] = Field(default_factory=list)


class PendingDecisionOut(BaseModel):
    id: str
    decision: str
    timestamp_seconds: Optional[float] = None
    timestamp_label: Optional[str] = None

    meeting_id: str
    meeting_title: str
    meeting_date: Optional[datetime] = None


class PendingDecisionsOut(BaseModel):
    total: int
    items: List[PendingDecisionOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class MeetingHitOut(BaseModel):
    id: str
    title: str
    status: str
    meeting_date: Optional[datetime] = None
    snippet: Optional[str] = Field(None, description="Where the term appeared")


class TranscriptHitOut(BaseModel):
    """
    A moment in a recording where the search term was spoken.

    Carries both the meeting and the offset, so a result can link straight to
    that point in the player rather than only to the meeting.
    """

    meeting_id: str
    meeting_title: str
    segment_index: int
    start_time: float
    start_label: str
    speaker: str
    speaker_name: Optional[str] = None
    snippet: str


class ActionItemHitOut(BaseModel):
    id: str
    meeting_id: str
    meeting_title: str
    task: str
    owner_name: Optional[str] = None
    deadline_date: Optional[date] = None
    deadline_raw: Optional[str] = None
    status: str = "open"


class DecisionHitOut(BaseModel):
    id: str
    meeting_id: str
    meeting_title: str
    decision: str
    timestamp_seconds: Optional[float] = None
    timestamp_label: Optional[str] = None
    status: str = "pending"


class SearchResultsOut(BaseModel):
    """
    Search across everything a meeting produced, not just its title.

    Grouped by what was matched so the UI can label results by kind. `truncated`
    says whether a group hit its per-group limit and has more behind it.
    """

    query: str
    total_results: int = 0
    truncated: bool = False

    meetings: List[MeetingHitOut] = Field(default_factory=list)
    transcript: List[TranscriptHitOut] = Field(default_factory=list)
    action_items: List[ActionItemHitOut] = Field(default_factory=list)
    decisions: List[DecisionHitOut] = Field(default_factory=list)