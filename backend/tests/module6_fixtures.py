"""
Module 6 - Dashboard & Meeting Details
Shared test fixtures.

Kept in its own module rather than a conftest.py so that adding module 6's tests
cannot change how the existing test files behave. Each test file imports the
fixtures it needs; pytest picks them up from the importing module's namespace.

Every test runs against a throwaway SQLite file with the database dependency
overridden, so nothing here touches a development or production database.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set before importing the app so its settings never resolve to a real database.
#
# Only DATABASE_URL and SECRET_KEY are touched, and both with setdefault. Other
# test files in this directory configure their environment the same way, and
# settings are read once at import: whichever module imports first wins. Setting
# a key this module does not need would silently change another module's tests
# depending on collection order, so nothing else is assigned here. In particular
# PIPELINE_SERVICE_KEY is left alone -- module 4's tests assert against it, and
# module 6 has no service-key endpoints.
os.environ.setdefault("SECRET_KEY", "module6-test-secret")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{Path(tempfile.gettempdir()) / 'module6_placeholder.db'}".replace("\\", "/"),
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.api import deps  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.db.database import Base  # noqa: E402
from app.db.models import (  # noqa: E402
    FileType,
    Meeting,
    MeetingFile,
    MeetingStatus,
    Participant,
    User,
)
from app.db.models_insights import (  # noqa: E402,F401
    ActionItem,
    Deadline,
    Decision,
    MeetingInsight,
    UnresolvedIssue,
)
from app.db.models_stt import MeetingTranscript, TranscriptSegment  # noqa: E402
from app.main import app  # noqa: E402
from app.services import insights_service  # noqa: E402


# A short meeting used by most tests: three speakers, two decisions, several
# tasks with deadlines phrased the way people actually say them.
SAMPLE_SEGMENTS = [
    (0.0, 12.0, "Speaker 1", "We need to settle the launch date and who owns the remaining work."),
    (12.0, 26.0, "Speaker 2", "The backend authentication service is not finished yet."),
    (26.0, 40.0, "Speaker 2", "I can have it wrapped up by Friday if nothing else lands on me."),
    (40.0, 55.0, "Speaker 1", "Good. So Ali will finish the backend by Friday."),
    (55.0, 68.0, "Speaker 3", "I'll complete the homepage by Friday as well."),
    (68.0, 82.0, "Speaker 1", "We decided to launch the product on September 1."),
    (82.0, 96.0, "Speaker 1", "The marketing budget is finalised at thirty thousand."),
    (96.0, 110.0, "Speaker 3", "We still have not resolved whether the mobile app ships at the same time."),
]

SAMPLE_ANALYSIS = {
    "summary_short": "Launch set for September 1 with backend and homepage work due Friday.",
    "summary_detailed": "The team agreed a September 1 launch date once the backend "
    "authentication service and homepage work land on Friday. The marketing budget "
    "was set at thirty thousand. Mobile app timing is still unresolved.",
    "key_points": ["Backend not finished", "Homepage due Friday", "Budget set at thirty thousand"],
    "decisions": [
        {"decision": "Launch the product on September 1", "timestamp": "1:08"},
        {"decision": "Set the marketing budget at thirty thousand", "timestamp": "1:22"},
    ],
    "action_items": [
        {"task": "Finish the backend authentication service", "owner": "Ali", "deadline": None, "deadline_raw": "Friday"},
        {"task": "Complete the homepage", "owner": "Hina", "deadline": None, "deadline_raw": "Friday"},
        {"task": "Confirm mobile app timing", "owner": "Hina", "deadline": None, "deadline_raw": "next Monday"},
    ],
    "unresolved_issues": [
        {"issue": "Whether the mobile app ships at the same time", "raised_by": "Hina"},
    ],
    "follow_up_items": ["Confirm app store review timeline"],
    "sentiment": "positive",
    "sentiment_notes": "Decisive, with one open question assigned.",
}


@pytest.fixture(scope="function")
def db_session():
    """A fresh SQLite database per test, deleted afterwards."""
    handle, path = tempfile.mkstemp(suffix=".db", prefix="module6_test_")
    os.close(handle)

    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.unlink(path)
        except (OSError, PermissionError):
            # Windows occasionally holds the handle briefly; a leftover temp file
            # is harmless and must not fail an otherwise passing test.
            pass


@pytest.fixture(scope="function")
def client(db_session):
    """A TestClient whose database dependency is bound to `db_session`."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[deps.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def user(db_session) -> User:
    record = User(
        email="owner@example.com",
        full_name="Meeting Owner",
        hashed_password=get_password_hash("ownerpass123"),
        is_active=True,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture(scope="function")
def other_user(db_session) -> User:
    """A second account, used to prove one user cannot read another's data."""
    record = User(
        email="intruder@example.com",
        full_name="Someone Else",
        hashed_password=get_password_hash("intruderpass123"),
        is_active=True,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def auth_headers(client: TestClient, email: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="function")
def headers(client, user) -> dict:
    return auth_headers(client, "owner@example.com", "ownerpass123")


@pytest.fixture(scope="function")
def other_headers(client, other_user) -> dict:
    return auth_headers(client, "intruder@example.com", "intruderpass123")


def make_meeting(
    db,
    owner: User,
    *,
    title: str = "Q3 Product Launch Planning",
    status: MeetingStatus = MeetingStatus.COMPLETED,
    days_ago: int = 2,
    duration: Optional[int] = 110,
    participants=(("Sara Khan", "Speaker 1"), ("Ali Raza", "Speaker 2"), ("Hina Malik", "Speaker 3")),
) -> Meeting:
    """Create a meeting with participants attached."""
    meeting = Meeting(
        owner_id=owner.id,
        title=title,
        description="Planning session for the upcoming release.",
        status=status,
        duration_seconds=duration,
        meeting_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(meeting)
    db.flush()

    for name, label in participants:
        db.add(
            Participant(
                meeting_id=meeting.id,
                name=name,
                email=f"{name.split()[0].lower()}@example.com",
                speaker_label=label,
            )
        )

    db.commit()
    db.refresh(meeting)
    return meeting


def add_transcript(db, meeting: Meeting, segments=SAMPLE_SEGMENTS) -> MeetingTranscript:
    """Attach a transcript and its segments, as module 4 would."""
    transcript = MeetingTranscript(
        meeting_id=meeting.id,
        raw_text=" ".join(s[3] for s in segments),
        formatted_text="\n".join(f"{s[2]}: {s[3]}" for s in segments),
        language="en",
        duration_seconds=segments[-1][1],
        overall_confidence=0.92,
        transcriber_model="whisper-base",
    )
    db.add(transcript)
    db.flush()

    for start, end, speaker, text in segments:
        db.add(
            TranscriptSegment(
                transcript_id=transcript.id,
                start_time=start,
                end_time=end,
                speaker_label=speaker,
                speaker_confidence=0.9,
                text=text,
                confidence=0.92,
            )
        )

    db.commit()
    db.refresh(transcript)
    return transcript


def add_insights(db, meeting: Meeting, analysis=None) -> MeetingInsight:
    """
    Store an analysis through the real persistence path.

    Deliberately not inserting rows directly: routing through the service means
    the tests also cover deadline resolution, owner matching and timestamp
    location rather than only the endpoints.
    """
    return insights_service.store_analysis(
        db,
        meeting,
        analysis or SAMPLE_ANALYSIS,
        segments=insights_service.load_transcript_segments(db, meeting.id),
        model_name="test-model",
    )


def add_recording(db, meeting: Meeting, tmp_path: Path, payload: bytes = b"") -> MeetingFile:
    """Attach a real file on disk so media streaming can be exercised."""
    payload = payload or bytes(range(256)) * 40  # 10,240 deterministic bytes

    meeting_dir = tmp_path / meeting.id
    meeting_dir.mkdir(parents=True, exist_ok=True)
    destination = meeting_dir / "recording.wav"
    destination.write_bytes(payload)

    record = MeetingFile(
        meeting_id=meeting.id,
        file_type=FileType.AUDIO,
        original_filename="recording.wav",
        storage_path=str(Path(meeting.id) / "recording.wav"),
        storage_backend="local",
        content_type="audio/wav",
        size_bytes=len(payload),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
