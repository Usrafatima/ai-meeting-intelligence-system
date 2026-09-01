
"""
Speech-to-Text Pipeline Service

Orchestrates:
1. Meeting file retrieval
2. Speech-to-text processing
3. Speaker mapping
4. Transcript storage in TranscriptChunk
5. Timestamp preservation

TranscriptChunk remains the single transcript storage model
for compatibility with Module 7 RAG + pgvector.
"""

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Meeting, Participant, TranscriptChunk
from app.services.storage import get_storage_backend
from app.services.speech_to_text import (
    get_speech_to_text_processor,
)

logger = logging.getLogger(__name__)


@dataclass
class SpeakerMapping:
    """Mapping between diarized speaker and meeting participant."""

    diarizer_speaker: str
    participant_id: Optional[str]
    participant_name: Optional[str]
    confidence: float


class STTPipeline:
    """
    Main speech-to-text pipeline.

    Gemini is selected first through the centralized
    speech_to_text service. Whisper can be used as fallback.

    Transcript segments are stored in TranscriptChunk.
    Embeddings remain NULL until Module 7 generates them.
    """

    def __init__(self, db: Session):
        self.db = db
        self.current_model = "unknown"

    async def process_meeting(
        self,
        meeting_id: int,
    ) -> Dict:
        """Process meeting audio/video and store transcript."""

        # ---------------------------------------------------------
        # 1. Get meeting
        # ---------------------------------------------------------

        meeting = (
            self.db.query(Meeting)
            .filter(Meeting.id == meeting_id)
            .first()
        )

        if not meeting:
            raise ValueError(
                f"Meeting {meeting_id} not found"
            )

        # ---------------------------------------------------------
        # 2. Update status
        # ---------------------------------------------------------

        meeting.status = "processing"
        self.db.commit()

        try:

            # -----------------------------------------------------
            # 3. Initialize storage backend
            # -----------------------------------------------------

            storage = get_storage_backend()
            del storage

            # -----------------------------------------------------
            # 4. Find audio/video files
            # -----------------------------------------------------

            media_files = []

            for meeting_file in meeting.files:

                file_type = str(
                    meeting_file.file_type
                ).lower()

                if file_type in {
                    "audio",
                    "filetype.audio",
                    "video",
                    "filetype.video",
                }:
                    media_files.append(
                        meeting_file
                    )

            if not media_files:
                raise ValueError(
                    f"No audio/video files found "
                    f"for meeting {meeting_id}"
                )

            # -----------------------------------------------------
            # 5. Get STT processor
            # -----------------------------------------------------

            processor = (
                await get_speech_to_text_processor()
            )

            self.current_model = getattr(
                processor,
                "MODEL_NAME",
                getattr(
                    processor,
                    "model_name",
                    getattr(
                        processor,
                        "model",
                        "unknown",
                    ),
                ),
            )

            # -----------------------------------------------------
            # 6. Process files
            # -----------------------------------------------------

            all_segments: List = []
            raw_text_parts: List[str] = []

            for meeting_file in media_files:

                storage_path = (
                    meeting_file.storage_path
                )

                if not storage_path:
                    logger.warning(
                        "Skipping file without storage path: %s",
                        meeting_file.id,
                    )
                    continue

                local_path: Optional[Path] = None
                temporary_file = False

                # -------------------------------------------------
                # Local storage
                # -------------------------------------------------

                if settings.STORAGE_BACKEND == "local":

                    candidate = Path(
                        storage_path
                    )

                    if candidate.is_absolute():
                        local_path = candidate
                    else:
                        local_path = (
                            Path(
                                settings.LOCAL_UPLOAD_DIR
                            )
                            / storage_path
                        )

                # -------------------------------------------------
                # Remote/S3 storage
                # -------------------------------------------------

                else:

                    downloaded_path = (
                        await self._download_s3_file(
                            storage_path
                        )
                    )

                    if downloaded_path:
                        local_path = Path(
                            downloaded_path
                        )
                        temporary_file = True

                # -------------------------------------------------
                # Validate path
                # -------------------------------------------------

                if local_path is None:
                    raise RuntimeError(
                        "Unable to resolve storage file: "
                        f"{storage_path}"
                    )

                if not local_path.exists():
                    raise FileNotFoundError(
                        "Meeting file does not exist: "
                        f"{local_path}"
                    )

                try:

                    # ---------------------------------------------
                    # Process audio
                    # ---------------------------------------------

                    result = (
                        await processor.process_audio(
                            str(local_path),
                            str(meeting_id),
                            meeting_file.original_filename
                            or "audio",
                        )
                    )

                    file_segments = getattr(
                        result,
                        "segments",
                        [],
                    )

                    file_raw_text = getattr(
                        result,
                        "raw_text",
                        "",
                    )

                    all_segments.extend(
                        file_segments
                    )

                    if file_raw_text:
                        raw_text_parts.append(
                            file_raw_text
                        )

                finally:

                    # ---------------------------------------------
                    # Remove temporary remote file
                    # ---------------------------------------------

                    if (
                        temporary_file
                        and local_path
                        and local_path.exists()
                    ):
                        try:
                            local_path.unlink()
                        except OSError as exc:
                            logger.warning(
                                "Could not remove temporary file "
                                "%s: %s",
                                local_path,
                                exc,
                            )

            # -----------------------------------------------------
            # 7. Validate transcription
            # -----------------------------------------------------

            if not all_segments and not raw_text_parts:
                raise ValueError(
                    "Speech-to-text returned no transcript"
                )

            # -----------------------------------------------------
            # 8. Build formatted transcript
            # -----------------------------------------------------

            formatted_text = (
                self._build_formatted_text(
                    all_segments
                )
            )

            raw_text_combined = "\n\n".join(
                raw_text_parts
            )

            # -----------------------------------------------------
            # 9. Map speakers
            # -----------------------------------------------------

            speaker_mappings = (
                self._map_speakers_to_participants(
                    meeting_id,
                    all_segments,
                )
            )

            # -----------------------------------------------------
            # 10. Update participant labels
            # -----------------------------------------------------

            await self._update_participant_labels(
                meeting_id,
                speaker_mappings,
            )

            # -----------------------------------------------------
            # 11. Save transcript chunks
            # -----------------------------------------------------

            self._save_transcript_chunks(
                meeting_id=meeting_id,
                segments=all_segments,
            )

            # -----------------------------------------------------
            # 12. Update meeting status
            # -----------------------------------------------------

            meeting.status = "transcribed"

            if all_segments:

                last_end_time = max(
                    float(
                        getattr(
                            segment,
                            "end_time",
                            0.0,
                        )
                    )
                    for segment in all_segments
                )

                meeting.duration_seconds = int(
                    last_end_time
                )

            self.db.commit()

            # -----------------------------------------------------
            # 13. Return response
            # -----------------------------------------------------

            return {
                "meeting_id": meeting_id,
                "status": "success",
                "raw_text": raw_text_combined,
                "formatted_text": formatted_text,
                "segments": all_segments,
                "speaker_mappings": [
                    {
                        "diarizer_speaker": (
                            mapping.diarizer_speaker
                        ),
                        "participant_id": (
                            mapping.participant_id
                        ),
                        "participant_name": (
                            mapping.participant_name
                        ),
                        "confidence": (
                            mapping.confidence
                        ),
                    }
                    for mapping in speaker_mappings
                ],
                "processing_time_seconds": int(
                    max(
                        (
                            float(
                                getattr(
                                    segment,
                                    "end_time",
                                    0.0,
                                )
                            )
                            for segment in all_segments
                        ),
                        default=0.0,
                    )
                ),
                "transcriber_model": (
                    self.current_model
                ),
            }

        except Exception:

            meeting.status = "failed"
            self.db.commit()

            logger.exception(
                "STT pipeline failed for meeting %s",
                meeting_id,
            )

            raise

    # =============================================================
    # FORMATTED TEXT
    # =============================================================

    def _build_formatted_text(
        self,
        segments: List,
    ) -> str:
        """Build speaker-labelled transcript."""

        if not segments:
            return ""

        formatted_lines = []

        for segment in segments:

            speaker = getattr(
                segment,
                "speaker",
                "Unknown Speaker",
            )

            text = getattr(
                segment,
                "text",
                "",
            )

            if not text:
                continue

            formatted_lines.append(
                f"{speaker}: {text}"
            )

        return "\n".join(
            formatted_lines
        )

    # =============================================================
    # SPEAKER MAPPING
    # =============================================================

    def _map_speakers_to_participants(
        self,
        meeting_id: int,
        segments: List,
    ) -> List[SpeakerMapping]:
        """
        Map diarized speakers to meeting participants.

        Current strategy:
        first speaker -> first participant
        second speaker -> second participant
        etc.
        """

        participants = (
            self.db.query(Participant)
            .filter(
                Participant.meeting_id
                == meeting_id
            )
            .all()
        )

        diarized_speakers = {}

        for segment in segments:

            speaker = getattr(
                segment,
                "speaker",
                None,
            )

            if not speaker:
                continue

            start = float(
                getattr(
                    segment,
                    "start_time",
                    0.0,
                )
            )

            end = float(
                getattr(
                    segment,
                    "end_time",
                    0.0,
                )
            )

            if speaker not in diarized_speakers:

                diarized_speakers[speaker] = {
                    "first_appearance": start,
                    "last_appearance": end,
                }

            else:

                diarized_speakers[speaker][
                    "first_appearance"
                ] = min(
                    diarized_speakers[speaker][
                        "first_appearance"
                    ],
                    start,
                )

                diarized_speakers[speaker][
                    "last_appearance"
                ] = max(
                    diarized_speakers[speaker][
                        "last_appearance"
                    ],
                    end,
                )

        speaker_keys = sorted(
            diarized_speakers.keys(),
            key=lambda speaker: (
                diarized_speakers[speaker][
                    "first_appearance"
                ]
            ),
        )

        mappings: List[SpeakerMapping] = []

        for index, speaker_key in enumerate(
            speaker_keys
        ):

            if index < len(participants):

                participant = participants[index]

                participant_name = getattr(
                    participant,
                    "name",
                    getattr(
                        participant,
                        "full_name",
                        None,
                    ),
                )

                mappings.append(
                    SpeakerMapping(
                        diarizer_speaker=speaker_key,
                        participant_id=str(
                            participant.id
                        ),
                        participant_name=(
                            participant_name
                        ),
                        confidence=0.85,
                    )
                )

            else:

                mappings.append(
                    SpeakerMapping(
                        diarizer_speaker=speaker_key,
                        participant_id=None,
                        participant_name=None,
                        confidence=0.70,
                    )
                )

        return mappings

    # =============================================================
    # SAVE TRANSCRIPT CHUNKS
    # =============================================================

    def _save_transcript_chunks(
        self,
        meeting_id: int,
        segments: List,
    ) -> None:
        """
        Save transcript segments to TranscriptChunk.

        Embedding remains NULL.

        Module 7 will generate Gemini embeddings later.
        """

        self.db.query(
            TranscriptChunk
        ).filter(
            TranscriptChunk.meeting_id
            == meeting_id
        ).delete(
            synchronize_session=False
        )

        saved_count = 0

        for segment in segments:

            text = getattr(
                segment,
                "text",
                "",
            )

            if not text or not text.strip():
                continue

            speaker = getattr(
                segment,
                "speaker",
                "Unknown Speaker",
            )

            start_time = float(
                getattr(
                    segment,
                    "start_time",
                    0.0,
                )
            )

            end_time = float(
                getattr(
                    segment,
                    "end_time",
                    0.0,
                )
            )

            content = (
                f"{speaker}: {text.strip()}"
            )

            transcript_chunk = TranscriptChunk(
                meeting_id=meeting_id,
                content=content,
                start_time=str(start_time),
                end_time=str(end_time),
                embedding=None,
            )

            self.db.add(
                transcript_chunk
            )

            saved_count += 1

        self.db.commit()

        logger.info(
            "Saved %d transcript chunks for meeting %s",
            saved_count,
            meeting_id,
        )

    # =============================================================
    # UPDATE PARTICIPANT LABELS
    # =============================================================

    async def _update_participant_labels(
        self,
        meeting_id: int,
        speaker_mappings: List[SpeakerMapping],
    ) -> None:
        """Update participant speaker labels."""

        for mapping in speaker_mappings:

            if not mapping.participant_id:
                continue

            participant = (
                self.db.query(Participant)
                .filter(
                    Participant.id
                    == mapping.participant_id
                )
                .first()
            )

            if participant:

                participant.speaker_label = (
                    mapping.diarizer_speaker
                )

                logger.info(
                    "Updated participant %s "
                    "with speaker label '%s'",
                    mapping.participant_name,
                    mapping.diarizer_speaker,
                )

        self.db.commit()

    # =============================================================
    # S3 DOWNLOAD
    # =============================================================

    async def _download_s3_file(
        self,
        s3_path: str,
    ) -> Optional[str]:
        """Download an S3 file to temporary storage."""

        try:

            import boto3

            s3_client = boto3.client(
                "s3",
                region_name=(
                    settings.STORAGE_REGION
                    or None
                ),
                endpoint_url=(
                    settings.STORAGE_ENDPOINT
                    or None
                ),
                aws_access_key_id=(
                    settings.STORAGE_ACCESS_KEY
                    or None
                ),
                aws_secret_access_key=(
                    settings.STORAGE_SECRET_KEY
                    or None
                ),
            )

            bucket = settings.STORAGE_BUCKET

            temp_file = (
                tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".audio",
                )
            )

            temp_file.close()

            s3_client.download_file(
                bucket,
                s3_path,
                temp_file.name,
            )

            return temp_file.name

        except Exception as exc:

            logger.error(
                "Failed to download S3 file: %s",
                exc,
            )

            return None

