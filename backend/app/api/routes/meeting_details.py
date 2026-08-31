"""
Module 6 - Dashboard & Meeting Details
The meeting details page: Overview, Transcript, AI Insights.

Every endpoint here is authenticated as a user and checks that the meeting
belongs to them. Module 4 already exposes a transcript route, but it is guarded
by a shared service key meant for pipeline-to-pipeline calls and performs no
ownership check, so it is not safe to put behind a browser. This module reads the
same tables through the user-facing auth that module 1 established, and leaves
module 4's route untouched for the pipeline's own use.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.db.models import Meeting, MeetingFile, User
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
from app.schemas.meeting_details import (
    ActionItemOut,
    ActionItemStatusUpdate,
    DeadlineOut,
    DecisionOut,
    DecisionStatusUpdate,
    GenerateInsightsRequest,
    MeetingCountsOut,
    MeetingInsightsOut,
    MeetingOverviewOut,
    MeetingTranscriptOut,
    MediaOut,
    ParticipantOut,
    SpeakerOut,
    TranscriptSegmentOut,
    UnresolvedIssueOut,
)
from app.services import insights_service
from app.services.insight_parsing import format_seconds_as_timestamp
from app.services.media_streaming import (
    build_range_response,
    guess_content_type,
    resolve_local_path,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def get_owned_meeting(db: Session, meeting_id: str, user_id: int) -> Meeting:
    """
    Fetch a meeting, refusing it unless the caller owns it.

    404 for missing, 403 for someone else's -- the same distinction module 3
    draws, so error handling stays consistent across the API.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found"
        )
    if meeting.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your meeting"
        )
    return meeting


def format_duration(seconds: Optional[float]) -> Optional[str]:
    """Render a duration the way it reads on a meeting card: '1h 04m', '7m 30s'."""
    if seconds is None or seconds < 0:
        return None

    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _due_fields(due: Optional[date]) -> tuple[bool, Optional[int]]:
    """Overdue flag and days remaining for a due date, both relative to today."""
    if due is None:
        return False, None
    delta = (due - date.today()).days
    return delta < 0, delta


def _enum_value(value: Any) -> Any:
    """Enum members serialise as their value; plain strings pass through."""
    return getattr(value, "value", value)


def _load_segments(db: Session, meeting_id: str) -> tuple[Optional[MeetingTranscript], List[TranscriptSegment]]:
    transcript = (
        db.query(MeetingTranscript)
        .filter(MeetingTranscript.meeting_id == meeting_id)
        .first()
    )
    if transcript is None:
        return None, []

    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.start_time.asc())
        .all()
    )
    return transcript, segments


def _participant_names(meeting: Meeting) -> Dict[str, str]:
    """Participant id -> name, for resolving speaker ids on transcript lines."""
    return {p.id: p.name for p in (meeting.participants or [])}


def _speaker_to_participant(meeting: Meeting) -> Dict[str, ParticipantOut]:
    """Diarised speaker label -> the participant module 4 matched it to."""
    return {
        p.speaker_label: p
        for p in (meeting.participants or [])
        if p.speaker_label
    }


def build_insights_payload(db: Session, meeting: Meeting) -> MeetingInsightsOut:
    """
    Assemble the AI Insights tab.

    Returns a well-formed empty payload with `available=False` when nothing has
    been analysed yet, rather than a 404 -- the tab exists either way and an
    empty state is not an error.
    """
    insight = (
        db.query(MeetingInsight)
        .filter(MeetingInsight.meeting_id == meeting.id)
        .first()
    )

    names = _participant_names(meeting)

    action_rows = (
        db.query(ActionItem)
        .filter(ActionItem.meeting_id == meeting.id)
        .order_by(ActionItem.deadline_date.is_(None), ActionItem.deadline_date.asc())
        .all()
    )
    action_items = []
    for row in action_rows:
        overdue, days = _due_fields(row.deadline_date)
        action_items.append(
            ActionItemOut(
                id=row.id,
                task=row.task,
                owner_name=row.owner_name,
                participant_id=row.participant_id,
                participant_name=names.get(row.participant_id),
                deadline_date=row.deadline_date,
                deadline_raw=row.deadline_raw,
                is_overdue=overdue and _enum_value(row.status) == "open",
                days_until_due=days,
                status=_enum_value(row.status),
                source_timestamp=row.source_timestamp,
                source_timestamp_label=format_seconds_as_timestamp(row.source_timestamp),
            )
        )

    decisions = [
        DecisionOut(
            id=row.id,
            decision=row.decision,
            timestamp_seconds=row.timestamp_seconds,
            timestamp_label=row.timestamp_label,
            status=_enum_value(row.status),
        )
        for row in db.query(Decision)
        .filter(Decision.meeting_id == meeting.id)
        .order_by(Decision.timestamp_seconds.is_(None), Decision.timestamp_seconds.asc())
        .all()
    ]

    deadlines = []
    for row in (
        db.query(Deadline)
        .filter(Deadline.meeting_id == meeting.id)
        .order_by(Deadline.due_date.is_(None), Deadline.due_date.asc())
        .all()
    ):
        overdue, days = _due_fields(row.due_date)
        deadlines.append(
            DeadlineOut(
                id=row.id,
                title=row.title,
                due_date=row.due_date,
                raw_phrase=row.raw_phrase,
                source=_enum_value(row.source),
                action_item_id=row.action_item_id,
                is_overdue=overdue,
                days_until_due=days,
            )
        )

    issues = [
        UnresolvedIssueOut(id=row.id, issue=row.issue, raised_by=row.raised_by)
        for row in db.query(UnresolvedIssue)
        .filter(UnresolvedIssue.meeting_id == meeting.id)
        .order_by(UnresolvedIssue.created_at.asc())
        .all()
    ]

    return MeetingInsightsOut(
        meeting_id=meeting.id,
        available=insight is not None,
        generated_at=insight.generated_at if insight else None,
        model_name=insight.model_name if insight else None,
        summary_short=insight.summary_short if insight else None,
        summary_detailed=insight.summary_detailed if insight else None,
        key_points=list(insight.key_points or []) if insight else [],
        follow_up_items=list(insight.follow_up_items or []) if insight else [],
        sentiment=insight.sentiment if insight else None,
        sentiment_notes=insight.sentiment_notes if insight else None,
        decisions=decisions,
        action_items=action_items,
        deadlines=deadlines,
        unresolved_issues=issues,
    )


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get(
    "/{meeting_id}/overview",
    response_model=MeetingOverviewOut,
    summary="Meeting overview",
    description=(
        "Everything the Overview tab needs in one call: summary, participants, "
        "detected speakers, duration, date, sentiment, headline counts and the "
        "streaming URL for the recording."
    ),
)
def get_meeting_overview(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    meeting = get_owned_meeting(db, meeting_id, current_user.id)

    transcript, segments = _load_segments(db, meeting.id)
    insight = (
        db.query(MeetingInsight)
        .filter(MeetingInsight.meeting_id == meeting.id)
        .first()
    )

    # Speakers are derived from the transcript rather than the diarisation table,
    # because segments are always written whereas diarisation rows are optional.
    speaker_map = _speaker_to_participant(meeting)
    grouped: Dict[str, Dict[str, Any]] = {}
    for segment in segments:
        label = segment.speaker_label or "Unknown"
        entry = grouped.setdefault(
            label,
            {"count": 0, "first": None, "last": None, "talk": 0.0, "speaker_id": None},
        )
        entry["count"] += 1
        start = float(segment.start_time or 0.0)
        end = float(segment.end_time) if segment.end_time is not None else start
        entry["first"] = start if entry["first"] is None else min(entry["first"], start)
        entry["last"] = end if entry["last"] is None else max(entry["last"], end)
        entry["talk"] += max(0.0, end - start)
        if segment.speaker_id and not entry["speaker_id"]:
            entry["speaker_id"] = segment.speaker_id

    names = _participant_names(meeting)
    speakers = []
    for label, entry in sorted(grouped.items(), key=lambda kv: kv[1]["first"] or 0.0):
        participant = speaker_map.get(label)
        participant_id = participant.id if participant else entry["speaker_id"]
        speakers.append(
            SpeakerOut(
                label=label,
                participant_id=participant_id,
                participant_name=names.get(participant_id) if participant_id else None,
                segment_count=entry["count"],
                first_appearance=entry["first"],
                last_appearance=entry["last"],
                speaking_seconds=round(entry["talk"], 2),
            )
        )

    # The recording to play. A meeting can carry several files; the first upload
    # is the one the player uses.
    media_file = (
        db.query(MeetingFile)
        .filter(MeetingFile.meeting_id == meeting.id)
        .order_by(MeetingFile.uploaded_at.asc())
        .first()
    )
    media = (
        MediaOut(
            file_id=media_file.id,
            filename=media_file.original_filename,
            file_type=_enum_value(media_file.file_type),
            content_type=media_file.content_type,
            size_bytes=media_file.size_bytes,
            stream_url=f"{settings.API_V1_STR}/meetings/{meeting.id}/media",
        )
        if media_file
        else None
    )

    today = date.today()
    counts = MeetingCountsOut(
        key_points=len(insight.key_points or []) if insight else 0,
        decisions_total=db.query(Decision).filter(Decision.meeting_id == meeting.id).count(),
        decisions_pending=db.query(Decision)
        .filter(
            Decision.meeting_id == meeting.id,
            Decision.status == DecisionStatus.PENDING,
        )
        .count(),
        action_items_total=db.query(ActionItem)
        .filter(ActionItem.meeting_id == meeting.id)
        .count(),
        action_items_open=db.query(ActionItem)
        .filter(
            ActionItem.meeting_id == meeting.id,
            ActionItem.status == ActionItemStatus.OPEN,
        )
        .count(),
        deadlines_total=db.query(Deadline).filter(Deadline.meeting_id == meeting.id).count(),
        deadlines_upcoming=db.query(Deadline)
        .filter(Deadline.meeting_id == meeting.id, Deadline.due_date >= today)
        .count(),
        unresolved_issues=db.query(UnresolvedIssue)
        .filter(UnresolvedIssue.meeting_id == meeting.id)
        .count(),
        participants=len(meeting.participants or []),
        transcript_segments=len(segments),
    )

    duration = meeting.duration_seconds
    if duration is None and transcript is not None:
        duration = int(transcript.duration_seconds) if transcript.duration_seconds else None

    return MeetingOverviewOut(
        id=meeting.id,
        title=meeting.title,
        description=meeting.description,
        status=_enum_value(meeting.status),
        meeting_date=meeting.meeting_date,
        created_at=meeting.created_at,
        duration_seconds=duration,
        duration_label=format_duration(duration),
        participants=[ParticipantOut.model_validate(p) for p in (meeting.participants or [])],
        speakers=speakers,
        summary_short=insight.summary_short if insight else None,
        summary_detailed=insight.summary_detailed if insight else None,
        sentiment=insight.sentiment if insight else None,
        sentiment_notes=insight.sentiment_notes if insight else None,
        has_transcript=bool(segments),
        has_insights=insight is not None,
        counts=counts,
        media=media,
    )


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


@router.get(
    "/{meeting_id}/transcript",
    response_model=MeetingTranscriptOut,
    summary="Speaker-labelled transcript, with search",
    description=(
        "Returns the transcript in start-time order, paginated so long recordings "
        "stay responsive. Supply `q` to return only the segments containing that "
        "text; `match_count` then reports the total number of hits across the "
        "whole transcript, not just the page being returned."
    ),
)
def get_meeting_transcript(
    meeting_id: str,
    q: Optional[str] = Query(
        None, min_length=1, max_length=200, description="Case-insensitive search within the transcript"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    meeting = get_owned_meeting(db, meeting_id, current_user.id)
    transcript, segments = _load_segments(db, meeting.id)

    names = _participant_names(meeting)
    speaker_map = _speaker_to_participant(meeting)

    # Index every segment against the full transcript before filtering, so a
    # search result still knows its true position in the recording.
    indexed = list(enumerate(segments))
    match_count: Optional[int] = None

    if q:
        needle = q.strip().lower()
        indexed = [pair for pair in indexed if needle in (pair[1].text or "").lower()]
        match_count = len(indexed)

    start = (page - 1) * page_size
    window = indexed[start : start + page_size]

    items = []
    for index, segment in window:
        label = segment.speaker_label or "Unknown"
        participant = speaker_map.get(label)
        participant_id = participant.id if participant else segment.speaker_id
        items.append(
            TranscriptSegmentOut(
                index=index,
                start_time=float(segment.start_time or 0.0),
                end_time=float(segment.end_time) if segment.end_time is not None else None,
                start_label=format_seconds_as_timestamp(float(segment.start_time or 0.0)) or "0:00",
                speaker=label,
                speaker_id=participant_id,
                speaker_name=names.get(participant_id) if participant_id else None,
                text=segment.text or "",
                confidence=segment.confidence,
            )
        )

    return MeetingTranscriptOut(
        meeting_id=meeting.id,
        language=(transcript.language if transcript else "en") or "en",
        duration_seconds=(
            transcript.duration_seconds if transcript else None
        ) or meeting.duration_seconds,
        transcriber_model=transcript.transcriber_model if transcript else None,
        overall_confidence=transcript.overall_confidence if transcript else None,
        total_segments=len(segments),
        query=q,
        match_count=match_count,
        page=page,
        page_size=page_size,
        segments=items,
    )


# ---------------------------------------------------------------------------
# AI Insights
# ---------------------------------------------------------------------------


@router.get(
    "/{meeting_id}/insights",
    response_model=MeetingInsightsOut,
    summary="Stored AI insights for a meeting",
    description=(
        "Key points, decisions, action items, deadlines and unresolved issues as "
        "stored by the last analysis. Returns 200 with `available: false` and "
        "empty collections when no analysis has been run yet."
    ),
)
def get_meeting_insights(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    meeting = get_owned_meeting(db, meeting_id, current_user.id)
    return build_insights_payload(db, meeting)


@router.post(
    "/{meeting_id}/insights/generate",
    response_model=MeetingInsightsOut,
    summary="Analyse the transcript and store the results",
    description=(
        "Runs the meeting intelligence analysis over the stored transcript and "
        "persists the outcome, replacing any previous pass. Statuses a user has "
        "already set on action items and decisions are carried across.\n\n"
        "409 when the meeting has no transcript yet; 503 when the analysis model "
        "is unconfigured or unreachable."
    ),
    responses={
        409: {"description": "No transcript stored for this meeting yet"},
        503: {"description": "Analysis model unavailable"},
    },
)
async def generate_meeting_insights(
    meeting_id: str,
    payload: GenerateInsightsRequest | None = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    meeting = get_owned_meeting(db, meeting_id, current_user.id)
    summary_mode = payload.summary_mode if payload else "detailed"

    try:
        await insights_service.generate_and_store(db, meeting, summary_mode)
    except insights_service.TranscriptNotReady as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except insights_service.AnalysisUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return build_insights_payload(db, meeting)


@router.patch(
    "/{meeting_id}/action-items/{action_item_id}",
    response_model=ActionItemOut,
    summary="Mark an action item open or done",
    description=(
        "Lets a user tick off extracted tasks. The dashboard's open action item "
        "count reads this field."
    ),
)
def update_action_item(
    meeting_id: str,
    action_item_id: str,
    payload: ActionItemStatusUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    meeting = get_owned_meeting(db, meeting_id, current_user.id)

    item = (
        db.query(ActionItem)
        .filter(ActionItem.id == action_item_id, ActionItem.meeting_id == meeting.id)
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Action item not found"
        )

    item.status = ActionItemStatus(payload.status)
    db.commit()
    db.refresh(item)

    overdue, days = _due_fields(item.deadline_date)
    return ActionItemOut(
        id=item.id,
        task=item.task,
        owner_name=item.owner_name,
        participant_id=item.participant_id,
        participant_name=_participant_names(meeting).get(item.participant_id),
        deadline_date=item.deadline_date,
        deadline_raw=item.deadline_raw,
        is_overdue=overdue and _enum_value(item.status) == "open",
        days_until_due=days,
        status=_enum_value(item.status),
        source_timestamp=item.source_timestamp,
        source_timestamp_label=format_seconds_as_timestamp(item.source_timestamp),
    )


@router.patch(
    "/{meeting_id}/decisions/{decision_id}",
    response_model=DecisionOut,
    summary="Confirm a decision, or return it to pending",
    description=(
        "Extracted decisions start as pending until a human confirms them. The "
        "dashboard's pending decisions tile reads this field."
    ),
)
def update_decision(
    meeting_id: str,
    decision_id: str,
    payload: DecisionStatusUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    meeting = get_owned_meeting(db, meeting_id, current_user.id)

    decision = (
        db.query(Decision)
        .filter(Decision.id == decision_id, Decision.meeting_id == meeting.id)
        .first()
    )
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found"
        )

    decision.status = DecisionStatus(payload.status)
    db.commit()
    db.refresh(decision)

    return DecisionOut(
        id=decision.id,
        decision=decision.decision,
        timestamp_seconds=decision.timestamp_seconds,
        timestamp_label=decision.timestamp_label,
        status=_enum_value(decision.status),
    )


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


@router.get(
    "/{meeting_id}/media",
    summary="Stream the meeting recording",
    description=(
        "Serves the recording with HTTP range support, which is what makes "
        "clicking a timestamp able to seek: the player requests only the byte "
        "range it needs and the server answers 206 Partial Content. A request "
        "without a Range header gets the whole file as 200."
    ),
    responses={
        200: {"description": "Whole file", "content": {"application/octet-stream": {}}},
        206: {"description": "Partial content for a range request"},
        404: {"description": "Meeting has no recording, or the file is missing from storage"},
        416: {"description": "Requested range not satisfiable"},
    },
)
def stream_meeting_media(
    meeting_id: str,
    file_id: Optional[str] = Query(
        None, description="Which recording to stream; defaults to the first uploaded"
    ),
    range_header: Optional[str] = Header(None, alias="Range"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Response:
    meeting = get_owned_meeting(db, meeting_id, current_user.id)

    query = db.query(MeetingFile).filter(MeetingFile.meeting_id == meeting.id)
    if file_id:
        query = query.filter(MeetingFile.id == file_id)

    media_file = query.order_by(MeetingFile.uploaded_at.asc()).first()
    if not media_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This meeting has no recording attached",
        )

    content_type = guess_content_type(
        media_file.original_filename, media_file.content_type
    )

    # An object store can serve ranges itself, and far closer to the user than we
    # can. Hand the player a short-lived signed URL instead of proxying bytes.
    if (media_file.storage_backend or settings.STORAGE_BACKEND) == "s3":
        return RedirectResponse(
            url=_presigned_media_url(media_file.storage_path),
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    path = resolve_local_path(settings.LOCAL_UPLOAD_DIR, media_file.storage_path)
    return build_range_response(
        path,
        filename=media_file.original_filename,
        content_type=content_type,
        range_header=range_header,
    )


def _presigned_media_url(storage_path: str, expires_in: int = 3600) -> str:
    """Signed URL for an object-store recording, valid for an hour."""
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - only when S3 is configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage support is not installed on this server",
        ) from exc

    client = boto3.client(
        "s3",
        region_name=settings.STORAGE_REGION or None,
        endpoint_url=settings.STORAGE_ENDPOINT or None,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY or None,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY or None,
    )
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.STORAGE_BUCKET, "Key": storage_path},
        ExpiresIn=expires_in,
    )
