"""
Module 6 - Dashboard & Meeting Details
Demo data for reviewing and testing this module.

Run from the backend directory:

    python scripts/seed_demo.py

Creates a demo user and four meetings chosen to cover every state the dashboard
and meeting details page have to render:

    1. Q3 Product Launch Planning   full transcript, insights, playable recording
    2. Weekly Engineering Sync      full transcript and insights, no recording
    3. Client Call - Acme Corp      transcript stored, never analysed
    4. Design Review: Onboarding    still processing, nothing stored yet

Meetings 3 and 4 exist on purpose: an empty state that renders correctly is as
much a part of the module as a populated one.

The insight rows are not written directly. The script builds the payload module 5
would return and passes it through app/services/insights_service.store_analysis,
so seeding exercises the real persistence path -- deadline resolution, participant
matching and timestamp location all run for real. That means this script doubles
as an end-to-end check of the module without needing an API key.

Safe to re-run: the demo user's existing meetings are removed first.
"""
from __future__ import annotations

import math
import struct
import sys
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow `python scripts/seed_demo.py` as well as `python -m scripts.seed_demo`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.db.models import (  # noqa: E402
    FileType,
    Meeting,
    MeetingFile,
    MeetingStatus,
    Participant,
    User,
)
from app.db.models_insights import ActionItemStatus, Decision, DecisionStatus  # noqa: E402
from app.db.models_stt import MeetingTranscript, TranscriptSegment  # noqa: E402
from app.services import insights_service  # noqa: E402

import app.db.models_insights  # noqa: E402,F401  - ensure tables are registered

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"
DEMO_NAME = "Demo Reviewer"


# ---------------------------------------------------------------------------
# Transcripts
# ---------------------------------------------------------------------------

# (start, end, speaker, text)
LAUNCH_MEETING = [
    (0.0, 11.5, "Speaker 1", "Alright, let's get started. We need to settle the launch date today, and confirm who owns the remaining work."),
    (11.5, 26.0, "Speaker 2", "Before we lock anything in, the backend authentication service isn't done yet. I don't want to commit to a date we can't hit."),
    (26.0, 32.0, "Speaker 1", "How much is left on it?"),
    (32.0, 44.5, "Speaker 2", "Roughly three days of work. I can have it wrapped up by Friday if nothing else lands on me."),
    (44.5, 55.0, "Speaker 1", "Good. So Ali will finish the backend by Friday, and QA picks it up from Monday."),
    (55.0, 68.0, "Speaker 3", "On the front end, the homepage still needs the new hero section and the pricing table. I'll complete the homepage by Friday as well."),
    (68.0, 82.0, "Speaker 1", "That gives us the following week for integration. We decided to launch the product on September 1."),
    (82.0, 95.0, "Speaker 3", "Are we announcing on the same day, or staggering the marketing?"),
    (95.0, 112.0, "Speaker 1", "Let's settle the budget first. Finance approved forty thousand for the launch campaign, but I want to hold ten back as contingency."),
    (112.0, 126.0, "Speaker 2", "So thirty thousand for the initial push. Is that split between paid ads and events?"),
    (126.0, 141.0, "Speaker 1", "Sixty forty in favour of paid. The marketing budget is finalised at thirty thousand for the launch push."),
    (141.0, 155.0, "Speaker 3", "One thing we haven't resolved is whether the mobile app ships at the same time. Nobody has confirmed the app store review will clear in time."),
    (155.0, 168.0, "Speaker 1", "Leave that open for now. Hina, can you get a written answer from the mobile team by next Monday?"),
    (168.0, 179.0, "Speaker 3", "Yes, I'll follow up with them and send a written summary before the end of this month."),
]

ENGINEERING_SYNC = [
    (0.0, 14.0, "Speaker 1", "Quick sync. Where are we on the database migration that was blocking the reporting work?"),
    (14.0, 31.0, "Speaker 2", "It ran on staging over the weekend and took about four hours. Production will be slower, so we should schedule a window."),
    (31.0, 44.0, "Speaker 1", "Can we do it out of hours on Saturday?"),
    (44.0, 58.5, "Speaker 2", "That works. I'll prepare the rollback script before Saturday so we're not improvising if it goes wrong."),
    (58.5, 72.0, "Speaker 1", "We agreed to run the production migration on Saturday night with a rollback plan ready."),
    (72.0, 88.0, "Speaker 2", "The other issue is test coverage on the payments module. It's sitting around forty percent and nobody owns it."),
    (88.0, 101.0, "Speaker 1", "Let's not decide that today. Add it to next week's agenda and we'll assign someone then."),
    (101.0, 118.0, "Speaker 2", "Fine. I'll also update the deployment runbook tomorrow so the on-call rota has the new steps."),
]

CLIENT_CALL = [
    (0.0, 16.0, "Speaker 1", "Thanks for making time. We wanted to walk through the reporting requirements before we scope the work."),
    (16.0, 35.0, "Speaker 2", "The main thing our team needs is a weekly export that finance can open directly in Excel."),
    (35.0, 52.0, "Speaker 1", "Understood. Would a scheduled email with the file attached work, or do you need it in a shared drive?"),
    (52.0, 70.0, "Speaker 2", "A shared drive is better. Email attachments get blocked by our security filter fairly often."),
]


# ---------------------------------------------------------------------------
# Analyses, in module 5's response shape
# ---------------------------------------------------------------------------

LAUNCH_ANALYSIS = {
    "summary_short": (
        "The team set September 1 as the product launch date and finalised a thirty thousand "
        "launch budget, with backend and homepage work both due Friday."
    ),
    "summary_detailed": (
        "The meeting opened on outstanding engineering work blocking a launch commitment. The "
        "backend authentication service was reported as roughly three days from completion, with "
        "Ali committing to finish by Friday and QA starting the following Monday. Hina confirmed "
        "the homepage hero section and pricing table would also be ready by Friday, leaving the "
        "following week clear for integration.\n\n"
        "On that basis the team set September 1 as the launch date. Discussion then moved to the "
        "campaign budget: finance had approved forty thousand, of which ten thousand was held back "
        "as contingency, leaving thirty thousand for the initial push split sixty forty in favour "
        "of paid advertising over events.\n\n"
        "One question was left open -- whether the mobile app can ship alongside the web launch, "
        "which depends on an app store review clearing in time. Hina agreed to get written "
        "confirmation from the mobile team by next Monday and circulate a summary before month end."
    ),
    "key_points": [
        "Backend authentication service is about three days from completion",
        "Homepage hero section and pricing table are the remaining front-end work",
        "Finance approved forty thousand, with ten thousand held back as contingency",
        "Campaign spend splits sixty forty between paid advertising and events",
        "Mobile app timing depends on an app store review that has not been confirmed",
    ],
    "decisions": [
        {"decision": "Launch the product on September 1", "timestamp": "1:08"},
        {"decision": "Set the marketing budget at thirty thousand for the launch push", "timestamp": "2:06"},
        {"decision": "QA begins on the backend authentication service from Monday", "timestamp": "0:44"},
    ],
    "action_items": [
        {"task": "Finish the backend authentication service", "owner": "Ali", "deadline": None, "deadline_raw": "Friday"},
        {"task": "Complete the homepage hero section and pricing table", "owner": "Hina", "deadline": None, "deadline_raw": "Friday"},
        {"task": "Get written confirmation from the mobile team on app store review timing", "owner": "Hina", "deadline": None, "deadline_raw": "next Monday"},
        {"task": "Circulate a written summary of the mobile team's response", "owner": "Hina", "deadline": None, "deadline_raw": "end of this month"},
    ],
    "unresolved_issues": [
        {"issue": "Whether the mobile app can ship at the same time as the web launch", "raised_by": "Hina"},
    ],
    "follow_up_items": [
        "Confirm the app store review timeline with the mobile team",
        "Share the final campaign budget breakdown with finance",
    ],
    "sentiment": "positive",
    "sentiment_notes": "Constructive and decisive; the one open question was acknowledged and assigned rather than left hanging.",
}

SYNC_ANALYSIS = {
    "summary_short": (
        "The production database migration was scheduled for Saturday night with a rollback plan, "
        "and payments test coverage was deferred to next week."
    ),
    "summary_detailed": (
        "The staging run of the database migration completed in around four hours, and the team "
        "agreed production would be slower and needed a dedicated out-of-hours window. Saturday "
        "night was chosen, with a rollback script to be prepared beforehand so that a failure does "
        "not have to be handled improvisationally.\n\n"
        "Test coverage on the payments module was raised as a concern at roughly forty percent with "
        "no clear owner. Rather than assign it in passing, it was deferred to next week's agenda. "
        "The deployment runbook is also being updated so the on-call rota reflects the new steps."
    ),
    "key_points": [
        "Staging migration completed in approximately four hours",
        "Production migration needs an out-of-hours window",
        "Payments module test coverage is around forty percent and unowned",
    ],
    "decisions": [
        {"decision": "Run the production database migration on Saturday night with a rollback plan ready", "timestamp": "0:58"},
    ],
    "action_items": [
        {"task": "Prepare the rollback script for the production migration", "owner": "Ali", "deadline": None, "deadline_raw": "before Saturday"},
        {"task": "Update the deployment runbook for the on-call rota", "owner": "Ali", "deadline": None, "deadline_raw": "tomorrow"},
        {"task": "Add payments test coverage ownership to next week's agenda", "owner": "Sara", "deadline": None, "deadline_raw": "next week"},
    ],
    "unresolved_issues": [
        {"issue": "Who owns raising test coverage on the payments module", "raised_by": "Ali"},
    ],
    "follow_up_items": ["Confirm the maintenance window with the on-call engineer"],
    "sentiment": "neutral",
    "sentiment_notes": "Routine status discussion; one concern raised and consciously deferred.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_demo_recording(destination: Path, duration_seconds: float) -> int:
    """
    Write a small WAV whose pitch rises over its length.

    A real audio file is needed for the media endpoint to be exercised
    meaningfully -- range requests, seeking and 206 responses are all invisible
    against a placeholder. The pitch climbs steadily so that when a reviewer
    clicks a timestamp, it is audible that playback actually jumped.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    frame_rate = 8000
    total_frames = int(frame_rate * duration_seconds)
    amplitude = 8000

    frames = bytearray()
    for frame in range(total_frames):
        progress = frame / max(1, total_frames)
        frequency = 220.0 + (progress * 440.0)  # 220Hz -> 660Hz across the file
        sample = int(amplitude * math.sin(2 * math.pi * frequency * (frame / frame_rate)))
        frames += struct.pack("<h", sample)

    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(frame_rate)
        handle.writeframes(bytes(frames))

    return destination.stat().st_size


def add_transcript(db, meeting: Meeting, lines, model: str = "whisper-base") -> None:
    """Store a transcript and its segments the way module 4 does."""
    raw_text = " ".join(line[3] for line in lines)
    formatted = "\n".join(f"{line[2]}: {line[3]}" for line in lines)

    transcript = MeetingTranscript(
        meeting_id=meeting.id,
        raw_text=raw_text,
        formatted_text=formatted,
        language="en",
        duration_seconds=lines[-1][1],
        overall_confidence=0.93,
        transcriber_model=model,
    )
    db.add(transcript)
    db.flush()

    for start, end, speaker, text in lines:
        db.add(
            TranscriptSegment(
                transcript_id=transcript.id,
                start_time=start,
                end_time=end,
                speaker_label=speaker,
                speaker_confidence=0.9,
                text=text,
                confidence=0.93,
            )
        )


def build_meeting(db, user: User, *, title, description, status, days_ago, duration, participants):
    """Create a meeting with its participants and return it."""
    meeting = Meeting(
        owner_id=user.id,
        title=title,
        description=description,
        status=status,
        duration_seconds=duration,
        meeting_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(meeting)
    db.flush()

    for name, email, speaker_label in participants:
        db.add(
            Participant(
                meeting_id=meeting.id,
                name=name,
                email=email,
                speaker_label=speaker_label,
            )
        )
    db.flush()
    db.refresh(meeting)
    return meeting


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                full_name=DEMO_NAME,
                hashed_password=get_password_hash(DEMO_PASSWORD),
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created demo user {DEMO_EMAIL}")
        else:
            print(f"Reusing demo user {DEMO_EMAIL}")

        # Re-runnable: clear this user's meetings, cascading to everything below.
        existing = db.query(Meeting).filter(Meeting.owner_id == user.id).all()
        for meeting in existing:
            db.delete(meeting)
        db.commit()
        if existing:
            print(f"Cleared {len(existing)} existing demo meeting(s)")

        # --- 1. Full meeting with a playable recording --------------------
        launch = build_meeting(
            db,
            user,
            title="Q3 Product Launch Planning",
            description="Settling the launch date, remaining engineering work and campaign budget.",
            status=MeetingStatus.COMPLETED,
            days_ago=2,
            duration=180,
            participants=[
                ("Sara Khan", "sara@example.com", "Speaker 1"),
                ("Ali Raza", "ali@example.com", "Speaker 2"),
                ("Hina Malik", "hina@example.com", "Speaker 3"),
            ],
        )
        add_transcript(db, launch, LAUNCH_MEETING)
        db.commit()

        upload_dir = Path(settings.LOCAL_UPLOAD_DIR)
        relative = Path(launch.id) / "q3-product-launch-planning.wav"
        size = write_demo_recording(upload_dir / relative, 180.0)
        db.add(
            MeetingFile(
                meeting_id=launch.id,
                file_type=FileType.AUDIO,
                original_filename="q3-product-launch-planning.wav",
                storage_path=str(relative),
                storage_backend="local",
                content_type="audio/wav",
                size_bytes=size,
            )
        )
        db.commit()
        print(f"  recording written: {size / 1024:.0f} KB")

        db.refresh(launch)
        insights_service.store_analysis(
            db,
            launch,
            LAUNCH_ANALYSIS,
            segments=insights_service.load_transcript_segments(db, launch.id),
            model_name="gemini-1.5-flash (seeded)",
        )

        # A user has already worked through part of this meeting, so the
        # dashboard shows a realistic mix rather than everything untouched.
        first_decision = (
            db.query(Decision)
            .filter(Decision.meeting_id == launch.id)
            .order_by(Decision.timestamp_seconds.asc())
            .first()
        )
        if first_decision:
            first_decision.status = DecisionStatus.CONFIRMED
        db.commit()

        # --- 2. Full meeting, no recording --------------------------------
        sync = build_meeting(
            db,
            user,
            title="Weekly Engineering Sync",
            description="Migration scheduling and outstanding test coverage.",
            status=MeetingStatus.COMPLETED,
            days_ago=5,
            duration=118,
            participants=[
                ("Sara Khan", "sara@example.com", "Speaker 1"),
                ("Ali Raza", "ali@example.com", "Speaker 2"),
            ],
        )
        add_transcript(db, sync, ENGINEERING_SYNC)
        db.commit()
        db.refresh(sync)
        insights_service.store_analysis(
            db,
            sync,
            SYNC_ANALYSIS,
            segments=insights_service.load_transcript_segments(db, sync.id),
            model_name="gemini-1.5-flash (seeded)",
        )

        # --- 3. Transcript stored, never analysed -------------------------
        client_call = build_meeting(
            db,
            user,
            title="Client Call - Acme Corp",
            description="Scoping conversation about reporting requirements.",
            status=MeetingStatus.TRANSCRIBED,
            days_ago=1,
            duration=70,
            participants=[
                ("Sara Khan", "sara@example.com", "Speaker 1"),
                ("Imran Sheikh", "imran@acme.example.com", "Speaker 2"),
            ],
        )
        add_transcript(db, client_call, CLIENT_CALL)
        db.commit()

        # --- 4. Still processing ------------------------------------------
        build_meeting(
            db,
            user,
            title="Design Review: Onboarding Flow",
            description="Walkthrough of the revised onboarding screens.",
            status=MeetingStatus.PROCESSING,
            days_ago=0,
            duration=None,
            participants=[("Hina Malik", "hina@example.com", None)],
        )
        db.commit()

        _report(db, user)

    finally:
        db.close()


def _report(db, user: User) -> None:
    """Print what was created, so a reviewer can see it worked without a client."""
    from app.db.models_insights import ActionItem, Deadline, UnresolvedIssue

    meetings = (
        db.query(Meeting)
        .filter(Meeting.owner_id == user.id)
        .order_by(Meeting.meeting_date.desc())
        .all()
    )

    print("\n" + "=" * 68)
    print(f"Seeded {len(meetings)} meetings for {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print("=" * 68)

    for meeting in meetings:
        actions = db.query(ActionItem).filter(ActionItem.meeting_id == meeting.id).count()
        open_actions = (
            db.query(ActionItem)
            .filter(
                ActionItem.meeting_id == meeting.id,
                ActionItem.status == ActionItemStatus.OPEN,
            )
            .count()
        )
        decisions = db.query(Decision).filter(Decision.meeting_id == meeting.id).count()
        deadlines = db.query(Deadline).filter(Deadline.meeting_id == meeting.id).count()
        dated = (
            db.query(Deadline)
            .filter(Deadline.meeting_id == meeting.id, Deadline.due_date.isnot(None))
            .count()
        )
        issues = (
            db.query(UnresolvedIssue)
            .filter(UnresolvedIssue.meeting_id == meeting.id)
            .count()
        )

        print(f"\n  {meeting.title}")
        print(f"    id       {meeting.id}")
        print(f"    status   {meeting.status.value}")
        print(
            f"    content  {actions} action items ({open_actions} open) | "
            f"{decisions} decisions | {deadlines} deadlines ({dated} with a resolved date) | "
            f"{issues} open issues"
        )

    print("\nStart the API with:  uvicorn app.main:app --reload")
    print("Then sign in at /api/v1/auth/login and open /docs to try the endpoints.\n")


if __name__ == "__main__":
    seed()
