"""
Module 6 - Dashboard & Meeting Details
The dashboard: aggregates and search across everything a user owns.

Each endpoint answers one of the things the brief asks the dashboard to show --
recent meetings, processing status, duration, action item counts, pending
decisions, upcoming deadlines and search -- computed on the server so the client
makes one request per panel instead of fetching every meeting and counting.

Every query is scoped to the signed-in user by joining through Meeting.owner_id,
which is indexed. A user can never see another user's aggregates.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models import Meeting, MeetingFile, MeetingStatus, Participant, User
from app.db.models_insights import (
    ActionItem,
    ActionItemStatus,
    Deadline,
    Decision,
    DecisionStatus,
    MeetingInsight,
    UnresolvedIssue,
)
from app.db.models_stt import MeetingTranscript, TranscriptSegment
from app.schemas.dashboard import (
    ActionItemHitOut,
    ActionItemStatsOut,
    DashboardStatsOut,
    DeadlineStatsOut,
    DecisionHitOut,
    DecisionStatsOut,
    MeetingHitOut,
    MeetingStatsOut,
    PendingDecisionOut,
    PendingDecisionsOut,
    RecentMeetingOut,
    RecentMeetingsOut,
    SearchResultsOut,
    TranscriptHitOut,
    UpcomingDeadlineOut,
    UpcomingDeadlinesOut,
)
from app.api.routes.meeting_details import format_duration
from app.services.insight_parsing import format_seconds_as_timestamp

router = APIRouter()

# Statuses that mean "the pipeline still has work to do" versus "there is
# something to read". Kept here so every panel groups them the same way.
IN_PROGRESS_STATUSES = {
    MeetingStatus.UPLOADED,
    MeetingStatus.QUEUED,
    MeetingStatus.PROCESSING,
}
READY_STATUSES = {
    MeetingStatus.TRANSCRIBED,
    MeetingStatus.ANALYZED,
    MeetingStatus.COMPLETED,
}


def _owned_meeting_ids(db: Session, user_id: int) -> List[str]:
    """Ids of every meeting belonging to the user, for scoping the child queries."""
    return [row[0] for row in db.query(Meeting.id).filter(Meeting.owner_id == user_id).all()]


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _snippet(text: str, needle: str, width: int = 160) -> str:
    """
    A window of `text` centred on the first occurrence of `needle`.

    Long transcript lines are unreadable in a result list, and the matched term
    is often nowhere near the start, so the excerpt is cut around the hit rather
    than truncated from the beginning.
    """
    if not text:
        return ""

    position = text.lower().find(needle.lower())
    if position == -1 or len(text) <= width:
        return text[:width] + ("..." if len(text) > width else "")

    start = max(0, position - width // 3)
    end = min(len(text), start + width)
    excerpt = text[start:end]

    return ("..." if start > 0 else "") + excerpt + ("..." if end < len(text) else "")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=DashboardStatsOut,
    summary="Headline dashboard numbers",
    description=(
        "Every count the dashboard header shows: meetings by processing status, "
        "total recorded duration, open and overdue action items, pending "
        "decisions, deadline counts and how many meetings are transcribed but "
        "not yet analysed."
    ),
)
def get_dashboard_stats(
    horizon_days: int = Query(
        7, ge=1, le=365, description="Window counted as 'upcoming' for deadlines"
    ),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    meeting_ids = _owned_meeting_ids(db, current_user.id)
    today = date.today()
    horizon = today + timedelta(days=horizon_days)

    # --- meetings ---------------------------------------------------------
    status_rows = (
        db.query(Meeting.status, func.count(Meeting.id))
        .filter(Meeting.owner_id == current_user.id)
        .group_by(Meeting.status)
        .all()
    )
    by_status: Dict[str, int] = {_enum_value(s): n for s, n in status_rows}

    meetings = MeetingStatsOut(
        total=sum(by_status.values()),
        processing=sum(by_status.get(_enum_value(s), 0) for s in IN_PROGRESS_STATUSES),
        completed=sum(by_status.get(_enum_value(s), 0) for s in READY_STATUSES),
        failed=by_status.get(_enum_value(MeetingStatus.FAILED), 0),
        by_status=by_status,
    )

    total_duration = (
        db.query(func.coalesce(func.sum(Meeting.duration_seconds), 0))
        .filter(Meeting.owner_id == current_user.id)
        .scalar()
        or 0
    )

    if not meeting_ids:
        return DashboardStatsOut(
            meetings=meetings,
            action_items=ActionItemStatsOut(),
            decisions=DecisionStatsOut(),
            deadlines=DeadlineStatsOut(),
            total_duration_seconds=int(total_duration),
            total_duration_label=format_duration(total_duration) or "0s",
            horizon_days=horizon_days,
        )

    # --- action items -----------------------------------------------------
    action_rows = (
        db.query(ActionItem.status, func.count(ActionItem.id))
        .filter(ActionItem.meeting_id.in_(meeting_ids))
        .group_by(ActionItem.status)
        .all()
    )
    action_counts = {_enum_value(s): n for s, n in action_rows}
    overdue_actions = (
        db.query(func.count(ActionItem.id))
        .filter(
            ActionItem.meeting_id.in_(meeting_ids),
            ActionItem.status == ActionItemStatus.OPEN,
            ActionItem.deadline_date.isnot(None),
            ActionItem.deadline_date < today,
        )
        .scalar()
        or 0
    )
    action_items = ActionItemStatsOut(
        total=sum(action_counts.values()),
        open=action_counts.get("open", 0),
        done=action_counts.get("done", 0),
        overdue=overdue_actions,
    )

    # --- decisions --------------------------------------------------------
    decision_rows = (
        db.query(Decision.status, func.count(Decision.id))
        .filter(Decision.meeting_id.in_(meeting_ids))
        .group_by(Decision.status)
        .all()
    )
    decision_counts = {_enum_value(s): n for s, n in decision_rows}
    decisions = DecisionStatsOut(
        total=sum(decision_counts.values()),
        pending=decision_counts.get("pending", 0),
        confirmed=decision_counts.get("confirmed", 0),
    )

    # --- deadlines --------------------------------------------------------
    def count_deadlines(*conditions) -> int:
        return (
            db.query(func.count(Deadline.id))
            .filter(Deadline.meeting_id.in_(meeting_ids), *conditions)
            .scalar()
            or 0
        )

    deadlines = DeadlineStatsOut(
        total=count_deadlines(Deadline.due_date.isnot(None)),
        overdue=count_deadlines(Deadline.due_date.isnot(None), Deadline.due_date < today),
        due_today=count_deadlines(Deadline.due_date == today),
        upcoming=count_deadlines(
            Deadline.due_date >= today, Deadline.due_date <= horizon
        ),
        unscheduled=count_deadlines(Deadline.due_date.is_(None)),
    )

    # --- everything else --------------------------------------------------
    unresolved = (
        db.query(func.count(UnresolvedIssue.id))
        .filter(UnresolvedIssue.meeting_id.in_(meeting_ids))
        .scalar()
        or 0
    )

    transcribed_ids = {
        row[0]
        for row in db.query(MeetingTranscript.meeting_id)
        .filter(MeetingTranscript.meeting_id.in_(meeting_ids))
        .all()
    }
    analysed_ids = {
        row[0]
        for row in db.query(MeetingInsight.meeting_id)
        .filter(MeetingInsight.meeting_id.in_(meeting_ids))
        .all()
    }

    return DashboardStatsOut(
        meetings=meetings,
        action_items=action_items,
        decisions=decisions,
        deadlines=deadlines,
        unresolved_issues=unresolved,
        awaiting_analysis=len(transcribed_ids - analysed_ids),
        total_duration_seconds=int(total_duration),
        total_duration_label=format_duration(total_duration) or "0s",
        horizon_days=horizon_days,
    )


# ---------------------------------------------------------------------------
# Recent meetings
# ---------------------------------------------------------------------------


@router.get(
    "/recent-meetings",
    response_model=RecentMeetingsOut,
    summary="Recent meetings with their counts resolved",
    description=(
        "The recent meetings list, each row already carrying its action item and "
        "pending decision counts, next deadline and short summary. Avoids the "
        "client issuing a follow-up request per meeting to populate the list."
    ),
)
def get_recent_meetings(
    limit: int = Query(5, ge=1, le=50),
    meeting_status: Optional[MeetingStatus] = Query(
        None, alias="status", description="Restrict to a single pipeline status"
    ),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    query = db.query(Meeting).filter(Meeting.owner_id == current_user.id)
    if meeting_status:
        query = query.filter(Meeting.status == meeting_status)

    total = query.count()
    meetings = (
        query.order_by(
            Meeting.meeting_date.desc().nullslast(), Meeting.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    if not meetings:
        return RecentMeetingsOut(total=total, items=[])

    ids = [m.id for m in meetings]

    # Counts are gathered in one grouped query per kind rather than per meeting,
    # so the panel costs a fixed number of queries no matter how long the list is.
    def grouped_count(model, *conditions) -> Dict[str, int]:
        rows = (
            db.query(model.meeting_id, func.count(model.id))
            .filter(model.meeting_id.in_(ids), *conditions)
            .group_by(model.meeting_id)
            .all()
        )
        return {meeting_id: count for meeting_id, count in rows}

    actions_total = grouped_count(ActionItem)
    actions_open = grouped_count(ActionItem, ActionItem.status == ActionItemStatus.OPEN)
    decisions_pending = grouped_count(
        Decision, Decision.status == DecisionStatus.PENDING
    )
    files = grouped_count(MeetingFile)
    participants = grouped_count(Participant)

    next_deadlines = {
        meeting_id: due
        for meeting_id, due in db.query(
            Deadline.meeting_id, func.min(Deadline.due_date)
        )
        .filter(Deadline.meeting_id.in_(ids), Deadline.due_date >= date.today())
        .group_by(Deadline.meeting_id)
        .all()
    }

    transcribed = {
        row[0]
        for row in db.query(MeetingTranscript.meeting_id)
        .filter(MeetingTranscript.meeting_id.in_(ids))
        .all()
    }
    insights = {
        row.meeting_id: row
        for row in db.query(MeetingInsight)
        .filter(MeetingInsight.meeting_id.in_(ids))
        .all()
    }

    items = []
    for meeting in meetings:
        insight = insights.get(meeting.id)
        due = next_deadlines.get(meeting.id)
        items.append(
            RecentMeetingOut(
                id=meeting.id,
                title=meeting.title,
                status=_enum_value(meeting.status),
                meeting_date=meeting.meeting_date,
                created_at=meeting.created_at,
                duration_seconds=meeting.duration_seconds,
                duration_label=format_duration(meeting.duration_seconds),
                participant_count=participants.get(meeting.id, 0),
                file_count=files.get(meeting.id, 0),
                has_transcript=meeting.id in transcribed,
                has_insights=insight is not None,
                action_items_total=actions_total.get(meeting.id, 0),
                action_items_open=actions_open.get(meeting.id, 0),
                decisions_pending=decisions_pending.get(meeting.id, 0),
                next_deadline=_as_date(due),
                summary_short=insight.summary_short if insight else None,
                sentiment=insight.sentiment if insight else None,
            )
        )

    return RecentMeetingsOut(total=total, items=items)


def _as_date(value: Any) -> Optional[date]:
    """SQLite returns aggregated dates as strings; normalise to a date."""
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Deadlines
# ---------------------------------------------------------------------------


@router.get(
    "/upcoming-deadlines",
    response_model=UpcomingDeadlinesOut,
    summary="Deadlines due across all meetings",
    description=(
        "Deadlines from every meeting the user owns, soonest first, within the "
        "requested number of days. Overdue items are included by default and "
        "flagged, since something already late is more urgent than something due "
        "next week, not less."
    ),
)
def get_upcoming_deadlines(
    days: int = Query(14, ge=1, le=365, description="How far ahead to look"),
    include_overdue: bool = Query(True, description="Include deadlines already past"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    today = date.today()
    horizon = today + timedelta(days=days)

    query = (
        db.query(Deadline, Meeting.title, ActionItem)
        .join(Meeting, Deadline.meeting_id == Meeting.id)
        .outerjoin(ActionItem, Deadline.action_item_id == ActionItem.id)
        .filter(Meeting.owner_id == current_user.id, Deadline.due_date.isnot(None))
        .filter(Deadline.due_date <= horizon)
    )
    if not include_overdue:
        query = query.filter(Deadline.due_date >= today)

    total = query.count()
    rows = query.order_by(Deadline.due_date.asc()).limit(limit).all()

    items = []
    for deadline, meeting_title, action_item in rows:
        due = _as_date(deadline.due_date)
        days_until = (due - today).days if due else None
        items.append(
            UpcomingDeadlineOut(
                id=deadline.id,
                title=deadline.title,
                due_date=due,
                raw_phrase=deadline.raw_phrase,
                source=_enum_value(deadline.source),
                meeting_id=deadline.meeting_id,
                meeting_title=meeting_title,
                action_item_id=deadline.action_item_id,
                owner_name=action_item.owner_name if action_item else None,
                action_item_status=_enum_value(action_item.status) if action_item else None,
                days_until_due=days_until,
                is_overdue=bool(due and due < today),
            )
        )

    return UpcomingDeadlinesOut(
        total=total, horizon_days=days, include_overdue=include_overdue, items=items
    )


@router.get(
    "/pending-decisions",
    response_model=PendingDecisionsOut,
    summary="Decisions awaiting confirmation",
    description=(
        "Extracted decisions nobody has confirmed yet, newest meeting first, each "
        "with the timestamp where it was made so it can be checked against the "
        "recording."
    ),
)
def get_pending_decisions(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    query = (
        db.query(Decision, Meeting.title, Meeting.meeting_date)
        .join(Meeting, Decision.meeting_id == Meeting.id)
        .filter(
            Meeting.owner_id == current_user.id,
            Decision.status == DecisionStatus.PENDING,
        )
    )

    total = query.count()
    rows = (
        query.order_by(Meeting.meeting_date.desc().nullslast(), Decision.timestamp_seconds.asc())
        .limit(limit)
        .all()
    )

    return PendingDecisionsOut(
        total=total,
        items=[
            PendingDecisionOut(
                id=decision.id,
                decision=decision.decision,
                timestamp_seconds=decision.timestamp_seconds,
                timestamp_label=decision.timestamp_label
                or format_seconds_as_timestamp(decision.timestamp_seconds),
                meeting_id=decision.meeting_id,
                meeting_title=title,
                meeting_date=meeting_date,
            )
            for decision, title, meeting_date in rows
        ],
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@router.get(
    "/search",
    response_model=SearchResultsOut,
    summary="Search meetings and everything inside them",
    description=(
        "Searches meeting titles and descriptions, the transcript itself, "
        "extracted action items and recorded decisions.\n\n"
        "Transcript hits carry the offset of the line that matched, so a result "
        "links to the moment the words were spoken rather than just to the "
        "meeting. Use `types` to restrict which groups are searched."
    ),
)
def search_meetings(
    q: str = Query(..., min_length=2, max_length=200, description="Text to search for"),
    types: Optional[str] = Query(
        None,
        description=(
            "Comma-separated subset of: meetings, transcript, action_items, "
            "decisions. Defaults to all four."
        ),
    ),
    limit_per_type: int = Query(10, ge=1, le=50),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    needle = q.strip()
    pattern = f"%{needle}%"

    requested = (
        {t.strip() for t in types.split(",") if t.strip()}
        if types
        else {"meetings", "transcript", "action_items", "decisions"}
    )

    meeting_ids = _owned_meeting_ids(db, current_user.id)
    results = SearchResultsOut(query=needle)

    if not meeting_ids:
        return results

    titles = {
        row[0]: row[1]
        for row in db.query(Meeting.id, Meeting.title)
        .filter(Meeting.owner_id == current_user.id)
        .all()
    }
    truncated = False

    # --- meetings ---------------------------------------------------------
    if "meetings" in requested:
        rows = (
            db.query(Meeting)
            .filter(
                Meeting.owner_id == current_user.id,
                or_(Meeting.title.ilike(pattern), Meeting.description.ilike(pattern)),
            )
            .order_by(Meeting.meeting_date.desc().nullslast())
            .limit(limit_per_type + 1)
            .all()
        )
        truncated = truncated or len(rows) > limit_per_type
        results.meetings = [
            MeetingHitOut(
                id=m.id,
                title=m.title,
                status=_enum_value(m.status),
                meeting_date=m.meeting_date,
                snippet=_snippet(m.description or m.title, needle),
            )
            for m in rows[:limit_per_type]
        ]

    # --- transcript -------------------------------------------------------
    if "transcript" in requested:
        rows = (
            db.query(TranscriptSegment, MeetingTranscript.meeting_id)
            .join(
                MeetingTranscript,
                TranscriptSegment.transcript_id == MeetingTranscript.id,
            )
            .filter(
                MeetingTranscript.meeting_id.in_(meeting_ids),
                TranscriptSegment.text.ilike(pattern),
            )
            .order_by(TranscriptSegment.start_time.asc())
            .limit(limit_per_type + 1)
            .all()
        )
        truncated = truncated or len(rows) > limit_per_type

        # A segment's index within its own transcript is what the details page
        # scrolls to, so it is resolved per meeting rather than guessed.
        index_cache: Dict[str, Dict[str, int]] = {}

        hits = []
        for segment, meeting_id in rows[:limit_per_type]:
            if meeting_id not in index_cache:
                ordered = (
                    db.query(TranscriptSegment.id)
                    .join(
                        MeetingTranscript,
                        TranscriptSegment.transcript_id == MeetingTranscript.id,
                    )
                    .filter(MeetingTranscript.meeting_id == meeting_id)
                    .order_by(TranscriptSegment.start_time.asc())
                    .all()
                )
                index_cache[meeting_id] = {row[0]: i for i, row in enumerate(ordered)}

            start = float(segment.start_time or 0.0)
            hits.append(
                TranscriptHitOut(
                    meeting_id=meeting_id,
                    meeting_title=titles.get(meeting_id, "Untitled meeting"),
                    segment_index=index_cache[meeting_id].get(segment.id, 0),
                    start_time=start,
                    start_label=format_seconds_as_timestamp(start) or "0:00",
                    speaker=segment.speaker_label or "Unknown",
                    speaker_name=None,
                    snippet=_snippet(segment.text or "", needle),
                )
            )
        results.transcript = hits

    # --- action items -----------------------------------------------------
    if "action_items" in requested:
        rows = (
            db.query(ActionItem)
            .filter(
                ActionItem.meeting_id.in_(meeting_ids),
                or_(ActionItem.task.ilike(pattern), ActionItem.owner_name.ilike(pattern)),
            )
            .order_by(ActionItem.deadline_date.is_(None), ActionItem.deadline_date.asc())
            .limit(limit_per_type + 1)
            .all()
        )
        truncated = truncated or len(rows) > limit_per_type
        results.action_items = [
            ActionItemHitOut(
                id=item.id,
                meeting_id=item.meeting_id,
                meeting_title=titles.get(item.meeting_id, "Untitled meeting"),
                task=item.task,
                owner_name=item.owner_name,
                deadline_date=item.deadline_date,
                deadline_raw=item.deadline_raw,
                status=_enum_value(item.status),
            )
            for item in rows[:limit_per_type]
        ]

    # --- decisions --------------------------------------------------------
    if "decisions" in requested:
        rows = (
            db.query(Decision)
            .filter(
                Decision.meeting_id.in_(meeting_ids),
                Decision.decision.ilike(pattern),
            )
            .order_by(Decision.timestamp_seconds.asc())
            .limit(limit_per_type + 1)
            .all()
        )
        truncated = truncated or len(rows) > limit_per_type
        results.decisions = [
            DecisionHitOut(
                id=item.id,
                meeting_id=item.meeting_id,
                meeting_title=titles.get(item.meeting_id, "Untitled meeting"),
                decision=item.decision,
                timestamp_seconds=item.timestamp_seconds,
                timestamp_label=item.timestamp_label,
                status=_enum_value(item.status),
            )
            for item in rows[:limit_per_type]
        ]

    results.truncated = truncated
    results.total_results = (
        len(results.meetings)
        + len(results.transcript)
        + len(results.action_items)
        + len(results.decisions)
    )
    return results
