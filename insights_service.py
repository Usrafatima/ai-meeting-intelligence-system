"""
Module 6 - Dashboard & Meeting Details
Turns module 5's analysis into stored, queryable rows.

Module 5 exposes a stateless endpoint: hand it a transcript, get structured
results back, nothing is kept. That is fine for a one-off analysis but cannot
support this module, whose dashboard has to answer questions like "how many
action items are still open across all my meetings" -- a query, not an analysis.

This service sits between the two. It reads the transcript module 4 stored,
calls module 5's processor unchanged, and writes the result into module 6's
tables. Module 5's code is imported, never edited.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from app.db.models import Meeting, Participant
from app.db.models_insights import (
    ActionItem,
    ActionItemStatus,
    Deadline,
    DeadlineSource,
    Decision,
    DecisionStatus,
    MeetingInsight,
    UnresolvedIssue,
)
from app.db.models_stt import MeetingTranscript, TranscriptSegment
from app.services.insight_parsing import (
    format_seconds_as_timestamp,
    parse_timestamp_to_seconds,
    resolve_deadline,
)

logger = logging.getLogger(__name__)


class InsightsError(Exception):
    """Base class for failures this service reports to its callers."""


class TranscriptNotReady(InsightsError):
    """The meeting has no stored transcript yet, so there is nothing to analyse."""


class AnalysisUnavailable(InsightsError):
    """The upstream analysis model could not be reached or is not configured."""


# Words too common to identify which part of a conversation a task came from.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "at", "by",
    "for", "with", "from", "will", "shall", "should", "would", "can", "could",
    "is", "are", "was", "were", "be", "been", "being", "do", "does", "did",
    "have", "has", "had", "i", "we", "you", "he", "she", "they", "it", "this",
    "that", "these", "those", "my", "our", "your", "their", "its", "as", "so",
    "if", "then", "than", "up", "out", "about", "into", "over", "after",
    "before", "next", "last", "get", "got", "make", "made", "need", "needs",
}


def _significant_words(text: str) -> set[str]:
    """Content words from a phrase, lowercased, stopwords and short tokens removed."""
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in tokens if len(t) > 2 and t not in _STOPWORDS}


def locate_segment_time(
    text: str, segments: Sequence[Dict[str, Any]], min_overlap: int = 2
) -> Optional[float]:
    """
    Find where in the recording a piece of extracted text was most likely said.

    Scores each transcript segment by how many content words it shares with
    `text` and returns the start time of the best match. Requires at least
    `min_overlap` shared words so that a weak coincidence does not send the
    player to the wrong moment -- returning None is preferable to returning a
    confidently wrong timestamp.
    """
    target = _significant_words(text)
    if len(target) < min_overlap:
        return None

    best_score = 0
    best_time: Optional[float] = None

    for segment in segments:
        overlap = len(target & _significant_words(segment.get("text", "")))
        if overlap > best_score:
            best_score = overlap
            best_time = segment.get("start_time")

    return best_time if best_score >= min_overlap else None


def load_transcript_segments(db: Session, meeting_id: str) -> List[Dict[str, Any]]:
    """
    Read the stored transcript for a meeting in the shape module 5 expects.

    Returns an empty list when nothing has been transcribed yet; callers decide
    whether that is an error in their context.
    """
    transcript = (
        db.query(MeetingTranscript)
        .filter(MeetingTranscript.meeting_id == meeting_id)
        .first()
    )
    if transcript is None:
        return []

    rows = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.start_time.asc())
        .all()
    )

    return [
        {
            "start_time": float(row.start_time or 0.0),
            "end_time": float(row.end_time) if row.end_time is not None else None,
            "speaker": row.speaker_label or "Unknown",
            "text": row.text or "",
        }
        for row in rows
    ]


def _anchor_date(meeting: Meeting) -> date:
    """
    The date relative deadlines are measured from.

    Prefers the meeting's own date so that reprocessing an old recording still
    yields the dates its participants meant, rather than dates relative to now.
    """
    if meeting.meeting_date:
        return meeting.meeting_date.date()
    if meeting.created_at:
        return meeting.created_at.date()
    return date.today()


def _match_participant(
    owner_name: Optional[str], participants: Sequence[Participant]
) -> Optional[str]:
    """
    Link an owner named in conversation to a participant record.

    Matches on full name, on the speaker label assigned by module 4, and on first
    name alone -- people are usually referred to by first name in a meeting. An
    ambiguous first name (two Alis) resolves to nothing rather than guessing.
    """
    if not owner_name:
        return None

    needle = owner_name.strip().lower()
    if not needle:
        return None

    for participant in participants:
        if (participant.name or "").strip().lower() == needle:
            return participant.id
        if (participant.speaker_label or "").strip().lower() == needle:
            return participant.id

    first_name_hits = [
        p for p in participants if (p.name or "").strip().lower().split(" ")[0] == needle
    ]
    if len(first_name_hits) == 1:
        return first_name_hits[0].id

    return None


def _existing_statuses(db: Session, meeting_id: str) -> tuple[dict, dict]:
    """
    Capture human-set statuses before the rows are replaced.

    Re-running the analysis rebuilds these tables. Without this, an action item a
    user ticked off would silently return to open after reprocessing, which reads
    as data loss. Keyed on normalised text, which survives cosmetic rewording.
    """
    action_states = {
        " ".join(_significant_words(item.task)): item.status
        for item in db.query(ActionItem).filter(ActionItem.meeting_id == meeting_id)
    }
    decision_states = {
        " ".join(_significant_words(item.decision)): item.status
        for item in db.query(Decision).filter(Decision.meeting_id == meeting_id)
    }
    return action_states, decision_states


def clear_stored_insights(db: Session, meeting_id: str) -> None:
    """Remove every insight row for a meeting. Does not commit."""
    for model in (Deadline, ActionItem, Decision, UnresolvedIssue, MeetingInsight):
        db.query(model).filter(model.meeting_id == meeting_id).delete(
            synchronize_session=False
        )


def store_analysis(
    db: Session,
    meeting: Meeting,
    analysis: Dict[str, Any],
    *,
    segments: Optional[Sequence[Dict[str, Any]]] = None,
    model_name: Optional[str] = None,
) -> MeetingInsight:
    """
    Write one analysis result into module 6's tables, replacing any earlier pass.

    `analysis` is module 5's response payload. Missing or malformed keys are
    tolerated: a model that returns partial output should still produce a usable
    meeting page rather than a 500.

    Commits before returning.
    """
    segments = segments or []
    anchor = _anchor_date(meeting)
    participants = list(meeting.participants or [])

    prior_actions, prior_decisions = _existing_statuses(db, meeting.id)
    clear_stored_insights(db, meeting.id)

    insight = MeetingInsight(
        meeting_id=meeting.id,
        summary_short=(analysis.get("summary_short") or "").strip() or None,
        summary_detailed=(analysis.get("summary_detailed") or "").strip() or None,
        key_points=[str(p) for p in (analysis.get("key_points") or []) if str(p).strip()],
        follow_up_items=[
            str(p) for p in (analysis.get("follow_up_items") or []) if str(p).strip()
        ],
        sentiment=(analysis.get("sentiment") or None),
        sentiment_notes=(analysis.get("sentiment_notes") or None),
        model_name=model_name,
    )
    db.add(insight)

    # --- Action items, and the deadlines they imply -----------------------
    for raw in analysis.get("action_items") or []:
        task = (raw.get("task") or "").strip()
        if not task:
            continue

        owner_name = (raw.get("owner") or "").strip() or None
        deadline_raw = (raw.get("deadline_raw") or "").strip() or None

        # Trust the model's resolved date when it gave one; fall back to
        # resolving the spoken phrase ourselves against the meeting date.
        deadline_date = _coerce_date(raw.get("deadline"))
        if deadline_date is None:
            deadline_date = resolve_deadline(deadline_raw, anchor)

        action_item = ActionItem(
            meeting_id=meeting.id,
            task=task,
            owner_name=owner_name,
            participant_id=_match_participant(owner_name, participants),
            deadline_date=deadline_date,
            deadline_raw=deadline_raw,
            status=prior_actions.get(
                " ".join(_significant_words(task)), ActionItemStatus.OPEN
            ),
            source_timestamp=locate_segment_time(task, segments),
        )
        db.add(action_item)
        db.flush()  # assign the id the deadline row points at

        if deadline_date or deadline_raw:
            db.add(
                Deadline(
                    meeting_id=meeting.id,
                    title=task,
                    due_date=deadline_date,
                    raw_phrase=deadline_raw,
                    source=DeadlineSource.ACTION_ITEM,
                    action_item_id=action_item.id,
                )
            )

    # --- Decisions --------------------------------------------------------
    for raw in analysis.get("decisions") or []:
        text = (raw.get("decision") or "").strip()
        if not text:
            continue

        seconds = parse_timestamp_to_seconds(raw.get("timestamp"))
        if seconds is None:
            seconds = locate_segment_time(text, segments)

        db.add(
            Decision(
                meeting_id=meeting.id,
                decision=text,
                timestamp_seconds=seconds,
                timestamp_label=format_seconds_as_timestamp(seconds),
                status=prior_decisions.get(
                    " ".join(_significant_words(text)), DecisionStatus.PENDING
                ),
            )
        )

    # --- Unresolved issues ------------------------------------------------
    for raw in analysis.get("unresolved_issues") or []:
        issue = (raw.get("issue") or "").strip()
        if not issue:
            continue
        db.add(
            UnresolvedIssue(
                meeting_id=meeting.id,
                issue=issue,
                raised_by=(raw.get("raised_by") or "").strip() or None,
            )
        )

    db.commit()
    db.refresh(insight)
    return insight


def _coerce_date(value: Any) -> Optional[date]:
    """Accept a date, or the 'YYYY-MM-DD' string module 5 returns."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


async def generate_and_store(
    db: Session, meeting: Meeting, summary_mode: str = "detailed"
) -> MeetingInsight:
    """
    Run module 5's analysis over the stored transcript and persist the result.

    Raises TranscriptNotReady when module 4 has not produced a transcript, and
    AnalysisUnavailable when the model is unconfigured or errors -- both of which
    the route layer turns into a clear HTTP status rather than a 500.
    """
    segments = load_transcript_segments(db, meeting.id)
    if not segments:
        raise TranscriptNotReady(
            "This meeting has no transcript yet. Run speech-to-text before requesting insights."
        )

    # Imported lazily: module 5 pulls in the Gemini SDK at construction time, and
    # this module is imported by the dashboard routes, which must work without it.
    from app.services.processors.gemini_intelligence_processor import (
        GeminiMeetingIntelligenceProcessor,
    )

    try:
        processor = GeminiMeetingIntelligenceProcessor()
    except Exception as exc:  # unconfigured key, SDK missing, no model available
        raise AnalysisUnavailable(f"Meeting analysis is not available: {exc}") from exc

    try:
        analysis = await processor.analyze(meeting.id, list(segments), summary_mode)
    except Exception as exc:
        logger.exception("Meeting intelligence analysis failed for %s", meeting.id)
        raise AnalysisUnavailable(f"Meeting analysis failed: {exc}") from exc

    model_name = getattr(getattr(processor, "model", None), "model_name", None)
    return store_analysis(
        db, meeting, analysis, segments=segments, model_name=model_name
    )