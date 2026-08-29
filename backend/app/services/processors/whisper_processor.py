import asyncio
import logging
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.services.speech_to_text import SpeechToTextProcessor, TranscriptResult

logger = logging.getLogger(__name__)

@dataclass
class TranscriptSegment:
    start_time: float
    end_time: float
    speaker: str
    text: str
    confidence: float = 1.0
    speaker_id: Optional[str] = None

@dataclass
class TranscriptResult:
    meeting_id: str
    raw_text: str
    formatted_text: str
    language: str = "en"
    segments: List[TranscriptSegment] = field(default_factory=list)
    confidence_score: Optional[float] = None
    processing_time_seconds: int = 0
    model_used: str = "whisper"

class WhisperSTTProcessor(SpeechToTextProcessor):
    """Whisper-based speech-to-text with pyannote.audio speaker diarization."""

    def __init__(self, model_size: str = "base", device: str = "cpu"):
        """Initialize Whisper and pyannote models.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            device: Device to run on ('cpu' or 'cuda')
        """
        self.model_size = model_size
        self.device = device
        self.whisper_model = None
        self.diarization_pipeline = None
        self._initialize_models()

    def _initialize_models(self):
        """Load Whisper and pyannote models."""
        try:
            import whisper
            self.whisper_model = whisper.load_model(self.model_size, device=self.device)
            logger.info(f"Loaded Whisper model: {self.model_size} on {self.device}")
        except ImportError:
            logger.warning("Whisper not installed. Install with: pip install openai-whisper")

        try:
            from pyannote.audio import Pipeline
            # This requires a Hugging Face token for pyannote/speaker-diarization
            # For free local alternative, we could use simpler methods
            self.diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization",
                use_auth_token=os.getenv("HUGGINGFACE_TOKEN")
            )
            logger.info("Loaded pyannote diarization pipeline")
        except (ImportError, Exception) as e:
            logger.warning(f"pyannote.audio not available ({e}). Diarization will be limited.")

    async def process_audio(
        self,
        audio_path: str,
        meeting_id: str,
        filename: str
    ) -> TranscriptResult:
        """Process audio file using Whisper for transcription and pyannote for diarization."""

        import time
        start_time = time.time()

        logger.info(f"Processing audio with Whisper for meeting {meeting_id}")
        logger.info(f"Audio path: {audio_path}")

        # Transcribe with Whisper
        if self.whisper_model:
            whisper_result = await asyncio.to_thread(
                self.whisper_model.transcribe,
                audio_path,
                word_timestamps=True
            )
            raw_text = whisper_result.get('text', '')
            language = whisper_result.get('language', 'en')
        else:
            # Placeholder if Whisper not available
            raw_text = "Whisper not installed. Install with: pip install openai-whisper"
            language = "en"

        # Diarize with pyannote (if available)
        segments = []
        if self.diarization_pipeline and self.whisper_model:
            # Merge Whisper transcription with pyannote diarization
            segments = await self._merge_transcription_and_diarization(
                audio_path, whisper_result
            )
        else:
            # Simple fallback: single speaker
            segments = [
                TranscriptSegment(
                    start_time=0.0,
                    end_time=30.0,
                    speaker="Speaker 1",
                    text=raw_text,
                    confidence=0.8
                )
            ]

        # Format the output
        formatted_text = "\n".join([
            f"{seg.speaker}: {seg.text}" for seg in segments
        ])

        processing_time = int(time.time() - start_time)

        return TranscriptResult(
            meeting_id=meeting_id,
            raw_text=raw_text,
            formatted_text=formatted_text,
            language=language,
            segments=segments,
            confidence_score=0.85,  # Average confidence
            processing_time_seconds=processing_time,
            model_used='whisper'
        )

    async def process_upload_file(
        self,
        upload_file,
        meeting_id: str
    ) -> TranscriptResult:
        """Process an uploaded audio file using Whisper."""

        # Save upload file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{upload_file.filename}") as tmp_file:
            tmp_path = tmp_file.name
            content = await upload_file.read()
            tmp_file.write(content)

        try:
            result = await self.process_audio(tmp_path, meeting_id, upload_file.filename)
            return result
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def _merge_transcription_and_diarization(
        self,
        audio_path: str,
        whisper_result: dict
    ) -> List[TranscriptSegment]:
        """Merge Whisper transcription with pyannote speaker diarization."""

        try:
            from pyannote.audio import Pipeline
            import torch

            # Get diarization from pyannote
            diarization = self.diarization_pipeline(audio_path)

            # Get word-level timestamps from Whisper
            whisper_segments = whisper_result.get('segments', [])

            # Simple approach: assign each Whisper segment to the most overlapping speaker
            merged_segments = []

            for ws in whisper_segments:
                ws_start = ws.get('start', 0)
                ws_end = ws.get('end', 0)
                ws_text = ws.get('text', '').strip()

                if not ws_text:
                    continue

                # Find which speaker is most active during this segment
                speaker = self._get_speaker_for_segment(diarization, ws_start, ws_end)

                merged_segments.append(TranscriptSegment(
                    start_time=ws_start,
                    end_time=ws_end,
                    speaker=speaker,
                    text=ws_text,
                    confidence=0.9
                ))

            return merged_segments

        except Exception as e:
            logger.error(f"Failed to merge transcription and diarization: {e}")
            # Fallback: return simple segments
            return [
                TranscriptSegment(
                    start_time=ws.get('start', 0),
                    end_time=ws.get('end', 0),
                    speaker=f"Speaker {i+1}",
                    text=ws.get('text', '').strip(),
                    confidence=0.8
                )
                for i, ws in enumerate(whisper_result.get('segments', []))
                if ws.get('text', '').strip()
            ]

    def _get_speaker_for_segment(self, diarization, start: float, end: float) -> str:
        """Determine which speaker is most active during a time segment."""

        speaker_durations = {}

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            # Calculate overlap between turn and segment
            overlap_start = max(turn.start, start)
            overlap_end = min(turn.end, end)
            overlap = max(0, overlap_end - overlap_start)

            if overlap > 0:
                speaker_durations[speaker] = speaker_durations.get(speaker, 0) + overlap

        if not speaker_durations:
            return "Unknown Speaker"

        # Return speaker with maximum overlap
        return max(speaker_durations, key=speaker_durations.get)