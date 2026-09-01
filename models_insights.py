"""
Module 6 - Dashboard & Meeting Details

Persistence layer for AI-derived meeting contents.

All meeting_id foreign keys use INTEGER because meetings.id
is an INTEGER primary key.
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
    Integer,
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
    OPEN = "open"
    DONE = "done"


class DecisionStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class DeadlineSource(str, enum.Enum):
    ACTION_ITEM = "action_item"
    DECISION = "decision"
    EXPLICIT = "explicit"


class MeetingInsight(Base):
    """
    AI analysis of a meeting.

    One row per meeting.
    """

    __tablename__ = "meeting_insights"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )

    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    summary_short = Column(
        Text,
        nullable=True,
    )

    summary_detailed = Column(
        Text,
        nullable=True,
    )

    key_points = Column(
        JSON,
        nullable=False,
        default=list,
    )

    follow_up_items = Column(
        JSON,
        nullable=False,
        default=list,
    )

    sentiment = Column(
        String(32),
        nullable=True,
    )

    sentiment_notes = Column(
        Text,
        nullable=True,
    )

    model_name = Column(
        String(128),
        nullable=True,
    )

    generated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    meeting = relationship(
        "Meeting",
        backref=backref(
            "insight",
            uselist=False,
            cascade="all, delete-orphan",
        ),
    )


class ActionItem(Base):
    """
    Task extracted from a meeting.
    """

    __tablename__ = "action_items"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )

    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    task = Column(
        Text,
        nullable=False,
    )

    owner_name = Column(
        String(255),
        nullable=True,
    )

    participant_id = Column(
        String,
        ForeignKey(
            "participants.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    deadline_date = Column(
        Date,
        nullable=True,
        index=True,
    )

    deadline_raw = Column(
        String(255),
        nullable=True,
    )

    status = Column(
        Enum(ActionItemStatus),
        nullable=False,
        default=ActionItemStatus.OPEN,
        server_default=ActionItemStatus.OPEN.value,
    )

    source_timestamp = Column(
        Float,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    meeting = relationship(
        "Meeting",
        backref=backref(
            "action_items",
            cascade="all, delete-orphan",
        ),
    )

    participant = relationship(
        "Participant",
    )

    __table_args__ = (
        Index(
            "ix_action_items_meeting_status",
            "meeting_id",
            "status",
        ),
    )


class Decision(Base):
    """
    Decision reached during a meeting.
    """

    __tablename__ = "decisions"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )

    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    decision = Column(
        Text,
        nullable=False,
    )

    timestamp_seconds = Column(
        Float,
        nullable=True,
    )

    timestamp_label = Column(
        String(16),
        nullable=True,
    )

    status = Column(
        Enum(DecisionStatus),
        nullable=False,
        default=DecisionStatus.PENDING,
        server_default=DecisionStatus.PENDING.value,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    meeting = relationship(
        "Meeting",
        backref=backref(
            "decisions",
            cascade="all, delete-orphan",
        ),
    )

    __table_args__ = (
        Index(
            "ix_decisions_meeting_status",
            "meeting_id",
            "status",
        ),
    )


class Deadline(Base):
    """
    Date commitment surfaced from a meeting.
    """

    __tablename__ = "deadlines"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )

    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(
        Text,
        nullable=False,
    )

    due_date = Column(
        Date,
        nullable=True,
        index=True,
    )

    raw_phrase = Column(
        String(255),
        nullable=True,
    )

    source = Column(
        Enum(DeadlineSource),
        nullable=False,
        default=DeadlineSource.EXPLICIT,
        server_default=DeadlineSource.EXPLICIT.value,
    )

    action_item_id = Column(
        String,
        ForeignKey(
            "action_items.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    meeting = relationship(
        "Meeting",
        backref=backref(
            "deadlines",
            cascade="all, delete-orphan",
        ),
    )

    action_item = relationship(
        "ActionItem",
        backref=backref(
            "deadline_entries",
        ),
    )


class UnresolvedIssue(Base):
    """
    An open question the meeting did not settle.
    """

    __tablename__ = "unresolved_issues"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )

    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    issue = Column(
        Text,
        nullable=False,
    )

    raised_by = Column(
        String(255),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    meeting = relationship(
        "Meeting",
        backref=backref(
            "unresolved_issues",
            cascade="all, delete-orphan",
        ),
    )