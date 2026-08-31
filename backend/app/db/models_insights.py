"""
Module 6 - Dashboard & Meeting Details
Persistence layer for the AI-derived contents of a meeting.

Module 5 (AI Meeting Intelligence) analyses a transcript and hands back structured
results, but keeps nothing. The dashboard has to report action item counts, pending
decisions and upcoming deadlines *across every meeting a user owns*, which is only
workable against stored rows -- re-running the analysis per request would be slow,
would cost an API call per meeting per page load, and would return different numbers
on every refresh.

These tables are owned by module 6 and written by app/services/insights_service.py.
They sit alongside models.py (module 3) and models_stt.py (module 4) without
modifying either.

Two status columns exist here that module 5 does not produce:

  * ActionItem.status    - open / done
  * Decision.status      - pending / confirmed

The brief asks the dashboard to show "pending decisions" and outstanding action
items. Neither is expressible without a status of some kind, so module 6 defines
them, defaulting to the not-yet-actioned value.
"""
import enum
import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from app.db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class ActionItemStatus(str, enum.Enum):
    """Whether an extracted task has been dealt with."""

    OPEN = "open"
    DONE = "done"


class DecisionStatus(str, enum.Enum):
    """Whether a decision has been confirmed by a human after extraction."""

    PENDING = "pending"
    CONFIRMED = "confirmed"


class DeadlineSource(str, enum.Enum):
    """Where a deadline row came from, so the UI can link back to it."""

    ACTION_ITEM = "action_item"
    DECISION = "decision"
    EXPLICIT = "explicit"


class MeetingInsight(Base):
    """
    The single AI analysis of a meeting: summaries, key points, sentiment.

    One row per meeting. Re-running the analysis replaces this row rather than
    adding to it, so the meeting details page always reflects the latest pass.
    """

    __tablename__ = "meeting_insights"

    id = Column(String, primary_key=True, default=generate_uuid)
    meeting_id = Column(
        String,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Both summary lengths are stored so the user can switch between
    # Short and Detailed without triggering another model call.
    summary_short = Column(Text, nullable=True)
    summary_detailed = Column(Text, nullable=True)

    key_points = Column(JSON, nullable=False, default=list)
    follow_up_items = Column(JSON, nullable=False, default=list)

    sentiment = Column(String(32), nullable=True)
    sentiment_notes = Column(Text, nullable=True)

    # Provenance: which model produced this, and when.
    model_name = Column(String(128), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting = relationship(
        "Meeting",
        backref=backref("insight", uselist=False, cascade="all, delete-orphan"),
    )


class ActionItem(Base):
    """
    A task extracted from the conversation: what, who, by when.

    deadline_date is the resolved calendar date where one could be worked out;
    deadline_raw keeps the phrase actually spoken ("end of this month") so the
    UI can show the human wording next to the parsed date.
    """

    __tablename__ = "action_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    meeting_id = Column(
        String,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    task = Column(Text, nullable=False)

    # Owner as spoken, plus a link to a real participant when one matches.
    owner_name = Column(String(255), nullable=True)
    participant_id = Column(
        String, ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )

    deadline_date = Column(Date, nullable=True, index=True)
    deadline_raw = Column(String(255), nullable=True)

    status = Column(
        Enum(ActionItemStatus),
        nullable=False,
        default=ActionItemStatus.OPEN,
        server_default=ActionItemStatus.OPEN.value,
    )

    # Offset in seconds into the recording where this task was raised, so the
    # player can jump to it. Nullable: not every item can be located.
    source_timestamp = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting = relationship(
        "Meeting", backref=backref("action_items", cascade="all, delete-orphan")
    )
    participant = relationship("Participant")

    __table_args__ = (
        # The dashboard's "open action items" count filters on both columns.
        Index("ix_action_items_meeting_status", "meeting_id", "status"),
    )


class Decision(Base):
    """
    A decision reached during the meeting.

    timestamp_seconds is the machine-usable offset for seeking the recording;
    timestamp_label is the same moment formatted for display ("32:45").
    """

    __tablename__ = "decisions"

    id = Column(String, primary_key=True, default=generate_uuid)
    meeting_id = Column(
        String,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    decision = Column(Text, nullable=False)

    timestamp_seconds = Column(Float, nullable=True)
    timestamp_label = Column(String(16), nullable=True)

    status = Column(
        Enum(DecisionStatus),
        nullable=False,
        default=DecisionStatus.PENDING,
        server_default=DecisionStatus.PENDING.value,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting = relationship(
        "Meeting", backref=backref("decisions", cascade="all, delete-orphan")
    )

    __table_args__ = (
        # Drives the dashboard's "pending decisions" tile.
        Index("ix_decisions_meeting_status", "meeting_id", "status"),
    )


class Deadline(Base):
    """
    A date commitment surfaced from the meeting, flattened into its own table.

    Action items already carry a deadline, but the dashboard needs "what is due
    across all my meetings, soonest first". Querying that from action_items alone
    would miss dates attached to decisions and dates mentioned with no owner, so
    every deadline is also recorded here with a pointer back to its origin.
    """

    __tablename__ = "deadlines"

    id = Column(String, primary_key=True, default=generate_uuid)
    meeting_id = Column(
        String,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(Text, nullable=False)
    due_date = Column(Date, nullable=True, index=True)
    raw_phrase = Column(String(255), nullable=True)

    source = Column(
        Enum(DeadlineSource),
        nullable=False,
        default=DeadlineSource.EXPLICIT,
        server_default=DeadlineSource.EXPLICIT.value,
    )
    action_item_id = Column(
        String, ForeignKey("action_items.id", ondelete="CASCADE"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meeting = relationship(
        "Meeting", backref=backref("deadlines", cascade="all, delete-orphan")
    )
    action_item = relationship("ActionItem", backref=backref("deadline_entries"))


class UnresolvedIssue(Base):
    """An open question the meeting did not settle."""

    __tablename__ = "unresolved_issues"

    id = Column(String, primary_key=True, default=generate_uuid)
    meeting_id = Column(
        String,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    issue = Column(Text, nullable=False)
    raised_by = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meeting = relationship(
        "Meeting", backref=backref("unresolved_issues", cascade="all, delete-orphan")
    )
