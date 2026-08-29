"""
Speech-to-Text Internal API Routes
Provides endpoints for the STT pipeline module to interact with the system.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.db.models import Meeting, Participant
from app.db.models_stt import MeetingTranscript, TranscriptSegment
from app.schemas.stt import (
    STTProcessingResponse,
    TranscriptResponse,
    SpeakerMappingUpdate,
    SpeakerMappingUpdateResponse,
)
from app.services.stt_pipeline import STTPipeline

router = APIRouter()


def verify_service_key(x_service_key: str = Header(...)) -> None:
    """Service-to-service auth for the pipeline modules."""
    if x_service_key != settings.PIPELINE_SERVICE_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service key"
        )


@router.post(
    "/meetings/{meeting_id}/process-stt",
    response_model=STTProcessingResponse,
    dependencies=[Depends(verify_service_key)],
)
async def process_speech_to_text(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Trigger speech-to-text processing for a meeting's audio files.

    This endpoint:
    1. Retrieves the meeting's uploaded audio files
    2. Runs speech-to-text transcription on them
    3. Performs speaker diarization
    4. Maps speakers to meeting participants
    5. Updates the meeting status to TRANSCRIBED

    Requires x-service-key header.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )

    # Update status to PROCESSING
    meeting.status = "processing"
    db.commit()

    pipeline = STTPipeline(db)

    try:
        result = await pipeline.process_meeting(meeting_id)
        return result

    except Exception as e:
        # Update status to FAILED on error
        meeting.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"STT processing failed: {str(e)}"
        )


@router.get(
    "/meetings/{meeting_id}/transcript",
    response_model=TranscriptResponse,
    dependencies=[Depends(verify_service_key)],
)
def get_meeting_transcript(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Retrieve the stored transcript for a meeting.

    Returns the raw text, formatted text with speaker labels,
    and segment data.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )

    transcript = (
        db.query(MeetingTranscript)
        .filter(MeetingTranscript.meeting_id == meeting_id)
        .first()
    )

    if transcript is None:
        # Nothing has been stored yet for this meeting
        return {
            "meeting_id": meeting_id,
            "raw_text": "",
            "formatted_text": "",
            "language": "en",
            "segments": [],
            "transcriber_model": None,
            "created_at": None,
        }

    segment_rows = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.transcript_id == transcript.id)
        .all()
    )

    return {
        "meeting_id": meeting_id,
        "raw_text": transcript.raw_text or "",
        "formatted_text": transcript.formatted_text or "",
        "language": transcript.language or "en",
        "segments": [
            {
                "start_time": float(seg.start_time) if seg.start_time else 0.0,
                "end_time": float(seg.end_time) if seg.end_time else 0.0,
                "speaker": seg.speaker_label or "Unknown",
                "text": seg.text or "",
                "confidence": float(seg.confidence) if seg.confidence is not None else 1.0,
                "speaker_id": seg.speaker_id,
            }
            for seg in segment_rows
        ],
        "overall_confidence": transcript.overall_confidence,
        "duration_seconds": meeting.duration_seconds,
        "transcriber_model": transcript.transcriber_model,
        "created_at": transcript.created_at,
    }


@router.post(
    "/meetings/{meeting_id}/speaker-mapping",
    response_model=SpeakerMappingUpdateResponse,
    dependencies=[Depends(verify_service_key)],
)
def update_speaker_mapping(
    meeting_id: str,
    mapping_data: SpeakerMappingUpdate,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Update speaker-to-participant mapping for a meeting.

    Allows the STT pipeline to refine speaker identifications
    after initial processing.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )

    # Update participant speaker labels
    mappings_count = 0
    for mapping in mapping_data.mappings:
        participant_id = mapping.participant_id
        speaker_label = mapping.speaker_label

        if participant_id and speaker_label:
            participant = (
                db.query(Participant)
                .filter(Participant.id == participant_id)
                .first()
            )
            if participant:
                participant.speaker_label = speaker_label
                mappings_count += 1

    db.commit()

    return {
        "meeting_id": meeting_id,
        "status": "success",
        "mappings_updated": mappings_count
    }