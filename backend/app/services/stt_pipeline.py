"""
Speech-to-Text Pipeline Service
Orchestrates the speech-to-text and speaker diarization workflow.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.db.database import SessionLocal
from sqlalchemy.orm import Session
from app.db.models import Meeting, Participant
from app.db.models_stt import MeetingTranscript, TranscriptSegment as TranscriptSegmentDB
from app.services.storage import get_storage_backend

logger = logging.getLogger(__name__)


@dataclass
class SpeakerMapping:
    """Mapping between diarized speaker and participant."""
    diarizer_speaker: str  # "Speaker 1", "Speaker 2", etc.
    participant_id: Optional[str]
    participant_name: Optional[str]
    confidence: float


class STTPipeline:
    """
    Main pipeline for speech-to-text and speaker identification.
    Provides endpoints that the internal API can call.
    """

    def __init__(self, db: Session):
        self.db = db

    async def process_meeting(
        self,
        meeting_id: str
    ) -> Dict:
        """
        Process a meeting's audio files through the STT pipeline.

        Args:
            meeting_id: The ID of the meeting to process

        Returns:
            Dictionary containing processing results
        """
        # 1. Get meeting details
        meeting = self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} not found")

        # 2. Update status to PROCESSING
        meeting.status = "processing"
        self.db.commit()

        # 3. Get audio files for this meeting
        storage = get_storage_backend()
        audio_files = [
            f for f in meeting.files if f.file_type == "audio"
        ]

        if not audio_files:
            # Try video files if no audio
            audio_files = [
                f for f in meeting.files if f.file_type == "video"
            ]

        if not audio_files:
            raise ValueError(f"No audio/video files found for meeting {meeting_id}")

        # 4. Process each audio file
        all_segments = []
        raw_text_parts = []

        for audio_file in audio_files:
            # Get storage path
            storage_path = audio_file.storage_path

            # For local storage, resolve to actual path
            if settings.STORAGE_BACKEND == "local":
                # storage_path may be an absolute path (e.g. "uploads/<id>/file.mp3")
                # or a relative one. Use it as-is if absolute, otherwise join.
                candidate = Path(storage_path)
                if candidate.is_absolute():
                    local_path = candidate
                else:
                    local_path = Path(settings.LOCAL_UPLOAD_DIR) / storage_path
            else:
                # For S3, download to temporary location
                local_path = await self._download_s3_file(storage_path)

            try:
                # 5. Call the STT processor
                processor = await self._get_stt_processor()
                result = await processor.process_audio(
                    str(local_path),
                    meeting_id,
                    audio_file.original_filename
                )

                all_segments.extend(result.segments)
                raw_text_parts.append(result.raw_text)

            finally:
                # Clean up temporary download if needed
                if settings.STORAGE_BACKEND != "local" and local_path and Path(local_path).exists():
                    Path(local_path).unlink()

        # 6. Build formatted text from segments
        formatted_text = self._build_formatted_text(all_segments)

        # 7. Map speakers to participants
        speaker_mappings = self._map_speakers_to_participants(
            meeting_id, all_segments
        )

        # 8. Update participant speaker labels in the database
        await self._update_participant_labels(meeting_id, speaker_mappings)

        # 9. Update meeting status
        meeting.status = "transcribed"
        meeting.duration_seconds = int(all_segments[-1].end_time) if all_segments else None
        self.db.commit()

        # 9b. Persist the transcript and its segments so the API can serve them later
        raw_text_combined = "\n\n".join(raw_text_parts)
        transcriber_model = getattr(self, 'current_model', 'unknown')
        self._save_transcript(
            meeting_id=meeting_id,
            raw_text=raw_text_combined,
            formatted_text=formatted_text,
            language="en",
            overall_confidence=None,
            transcriber_model=transcriber_model,
            segments=all_segments,
        )

        # 10. Return results
        return {
            "meeting_id": meeting_id,
            "status": "success",
            "raw_text": "\n\n".join(raw_text_parts),
            "formatted_text": formatted_text,
            "segments": all_segments,
            "speaker_mappings": [
                {"diarizer_speaker": s.diarizer_speaker, "participant_id": s.participant_id}
                for s in speaker_mappings
            ],
            "processing_time_seconds": len(all_segments),
            "transcriber_model": getattr(self, 'current_model', 'unknown')
        }

    async def _get_stt_processor(self):
        """Get the appropriate STT processor based on available configuration."""
        # If Gemini API key is available, use Gemini processor
        gemini_key = settings.GEMINI_API_KEY or ""
        if gemini_key and not gemini_key.startswith("your-"):
            try:
                from app.services.processors.gemini_processor import GeminiSTTProcessor
                return GeminiSTTProcessor()
            except (ImportError, ValueError) as e:
                logger.warning(f"Gemini processor not available: {e}")

        # Fall back to Whisper if installed
        try:
            from app.services.processors.whisper_processor import WhisperSTTProcessor
            return WhisperSTTProcessor()
        except ImportError as e:
            logger.warning(f"Whisper processor not available: {e}")

        # If neither is available, raise an error
        raise RuntimeError(
            "No STT processor available. Please configure GEMINI_API_KEY or install openai-whisper."
        )

    def _build_formatted_text(self, segments: List) -> str:
        """Build formatted text with speaker labels from segments."""
        if not segments:
            return ""

        formatted_lines = []
        for segment in segments:
            line = f"{segment.speaker}: {segment.text}"
            formatted_lines.append(line)

        return "\n".join(formatted_lines)

    def _map_speakers_to_participants(
        self,
        meeting_id: str,
        segments: List
    ) -> List[SpeakerMapping]:
        """
        Map diarized speakers to actual meeting participants.

        Strategy:
        1. If participant list is known (from Meeting.Create), try to match
           by name/email from transcription context
        2. Otherwise, assign "Speaker 1", "Speaker 2", etc. to participants
        """
        # Get meeting participants
        participants = (
            self.db.query(Participant)
            .filter(Participant.meeting_id == meeting_id)
            .all()
        )

        # Extract unique diarized speakers from segments
        diarized_speakers = {}
        for segment in segments:
            speaker = getattr(segment, 'speaker', None)
            if speaker and speaker not in diarized_speakers:
                diarized_speakers[speaker] = {
                    'segments': [],
                    'first_appearance': float('inf'),
                    'last_appearance': 0
                }
            if speaker:
                diarized_speakers[speaker]['segments'].append(segment)
                start = getattr(segment, 'start_time', 0)
                end = getattr(segment, 'end_time', 0)
                diarized_speakers[speaker]['first_appearance'] = min(
                    diarized_speakers[speaker]['first_appearance'], start
                )
                diarized_speakers[speaker]['last_appearance'] = max(
                    diarized_speakers[speaker]['last_appearance'], end
                )

        # Create speaker mappings
        mappings = []
        speaker_keys = sorted(diarized_speakers.keys(), key=lambda s: diarized_speakers[s]['first_appearance'])

        for i, speaker_key in enumerate(speaker_keys):
            if i < len(participants):
                # Map to existing participant
                participant = participants[i]
                mappings.append(SpeakerMapping(
                    diarizer_speaker=speaker_key,
                    participant_id=participant.id,
                    participant_name=participant.name,
                    confidence=0.85  # Default confidence, could be improved
                ))
            else:
                # Unknown speaker beyond known participants
                mappings.append(SpeakerMapping(
                    diarizer_speaker=speaker_key,
                    participant_id=None,
                    participant_name=None,
                    confidence=0.7
                ))

        return mappings

    def _save_transcript(
        self,
        meeting_id: str,
        raw_text: str,
        formatted_text: str,
        language: str,
        overall_confidence: Optional[float],
        transcriber_model: Optional[str],
        segments: List,
    ) -> None:
        """Upsert the meeting's transcript + segments so the API can serve them."""
        transcript = (
            self.db.query(MeetingTranscript)
            .filter(MeetingTranscript.meeting_id == meeting_id)
            .first()
        )
        if transcript is None:
            transcript = MeetingTranscript(meeting_id=meeting_id)
            self.db.add(transcript)
            self.db.flush()  # get transcript.id for child segments
        transcript.raw_text = raw_text
        transcript.formatted_text = formatted_text
        transcript.language = language
        transcript.overall_confidence = overall_confidence
        transcript.transcriber_model = transcriber_model

        # Replace old segments with the fresh set
        self.db.query(TranscriptSegmentDB).filter(
            TranscriptSegmentDB.transcript_id == transcript.id
        ).delete()
        for idx, seg in enumerate(segments):
            self.db.add(TranscriptSegmentDB(
                transcript_id=transcript.id,
                start_time=float(getattr(seg, 'start_time', 0.0)),
                end_time=float(getattr(seg, 'end_time', 0.0)),
                speaker_label=getattr(seg, 'speaker', 'Unknown'),
                text=getattr(seg, 'text', ''),
                confidence=float(getattr(seg, 'confidence', 1.0)) if getattr(seg, 'confidence', None) is not None else None,
                speaker_id=getattr(seg, 'speaker_id', None),
            ))
        self.db.commit()

    async def _update_participant_labels(
        self,
        meeting_id: str,
        speaker_mappings: List[SpeakerMapping]
    ):
        """Update participant speaker labels in the database."""

        for mapping in speaker_mappings:
            if mapping.participant_id:
                participant = (
                    self.db.query(Participant)
                    .filter(Participant.id == mapping.participant_id)
                    .first()
                )
                if participant:
                    participant.speaker_label = mapping.diarizer_speaker
                    self.db.commit()
                    logger.info(
                        f"Updated participant {participant.name} with speaker label '{mapping.diarizer_speaker}'"
                    )

    async def _download_s3_file(self, s3_path: str) -> Optional[str]:
        """Download a file from S3 storage to a temporary path."""
        try:
            import boto3
            import tempfile

            s3_client = boto3.client(
                "s3",
                region_name=settings.STORAGE_REGION or None,
                endpoint_url=settings.STORAGE_ENDPOINT or None,
                aws_access_key_id=settings.STORAGE_ACCESS_KEY or None,
                aws_secret_access_key=settings.STORAGE_SECRET_KEY or None,
            )

            bucket = settings.STORAGE_BUCKET
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
            s3_client.download_fileobj(bucket, s3_path, temp_file)
            temp_file.flush()

            return temp_file.name

        except Exception as e:
            logger.error(f"Failed to download S3 file: {e}")
            return None