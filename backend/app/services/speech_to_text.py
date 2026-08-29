import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import UploadFile

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Meeting, Participant

logger = logging.getLogger(__name__)
@dataclass
class TranscriptSegment:
    """Represents a single segment of transcript with speaker information."""

    start_time: float
    end_time: float
    speaker: str
    text: str
    confidence: float = 1.0
    speaker_id: Optional[str] = None  # For matching to participant records
@dataclass
class TranscriptResult:
    """Complete transcript result for a meeting audio file."""

    meeting_id: str
    raw_text: str
    formatted_text: str
    language: str = "en"
    segments: List[TranscriptSegment] = field(default_factory=list)
    confidence_score: Optional[float] = None
    processing_time_seconds: int = 0
    model_used: str = "gemini"
class SpeechToTextProcessor(ABC):
    """Abstract base class for speech-to-text and speaker diarization processors."""

    @abstractmethod
    async def process_audio(
        self,
        audio_path: str,
        meeting_id: str,
        filename: str
    ) -> TranscriptResult:
        """Process an audio file and return transcript with speaker identification.

        Args:
            audio_path: Path to the audio file
            meeting_id: ID of the meeting
            filename: Original filename (may contain extensions)

        Returns:
            TranscriptResult containing transcript data
        """
        pass

    @abstractmethod
    async def process_upload_file(
        self,
        upload_file: UploadFile,
        meeting_id: str
    ) -> TranscriptResult:
        """Process an uploaded audio file and return transcript with speaker identification.

        Args:
            upload_file: FastAPI UploadFile object
            meeting_id: ID of the meeting

        Returns:
            TranscriptResult containing transcript data
        """
        pass
class GeminiSTTProcessor(SpeechToTextProcessor):
    """Gemini-based speech-to-text and speaker diarization processor."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured in settings")

        # Initialize Gemini client
        try:
            import google.generativeai as genai
            self.genai = genai
            self.genai.configure(api_key=self.api_key)
            self.model = self.genai.GenerativeModel('gemini-1.5-pro-latest')
        except ImportError:
            raise ImportError("google-generativeai package not installed")

    async def process_audio(
        self,
        audio_path: str,
        meeting_id: str,
        filename: str
    ) -> TranscriptResult:
        """Process audio file using Gemini for transcription and speaker identification."""

        import time
        start_time = time.time()

        # Convert audio to format Gemini can process if needed
        processed_path = await self._prepare_audio_file(audio_path)

        try:
            # Generate content - Gemini can handle audio transcription and diarization
            with open(processed_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()

            # Create prompt for meeting transcription with speaker identification
            prompt = self._create_transcription_prompt()

            # Generate content with audio
            response = await asyncio.to_thread(
                self.model.generate_content,
                [prompt, {'mime_type': 'audio/mpeg', 'data': audio_bytes}]
            )

            # Parse Gemini response
            result = self._parse_gemini_response(response.text)

            processing_time = time.time() - start_time

            # Store original audio path
            original_path = processed_path

        finally:
            # Clean up temporary file
            Path(processed_path).unlink(missing_ok=True)

        return TranscriptResult(
            meeting_id=meeting_id,
            raw_text=result.get('raw_text', ''),
            formatted_text=result.get('formatted_text', ''),
            language=result.get('language', 'en'),
            segments=result.get('segments', []),
            confidence_score=result.get('confidence_score'),
            processing_time_seconds=int(processing_time),
            model_used='gemini'
        )

    async def process_upload_file(
        self,
        upload_file: UploadFile,
        meeting_id: str
    ) -> TranscriptResult:
        """Process uploaded file using Gemini."""

        # Save upload file to temporary location
        temp_path = f"/tmp/{meeting_id}_audio_{upload_file.filename}"

        try:
            # Read file content
            content = await upload_file.read()

            # Save to temp file
            with open(temp_path, 'wb') as f:
                f.write(content)

            # Process using the same method
            return await self.process_audio(temp_path, meeting_id, upload_file.filename)

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _create_transcription_prompt(self) -> str:
        """Create a detailed prompt for Gemini to transcribe and identify speakers."""

        return """
Please transcribe this meeting audio and identify speakers. For each segment of speech, provide:

1. Exact timestamps (start and end time in seconds)
2. The speaker identifier (Speaker 1, Speaker 2, etc.)
3. The transcribed text
4. Confidence score (0.0-1.0)
5. Key topics or keywords

Structure the response as JSON with this format:
{
  "raw_text": "Complete transcription...".
  "formatted_text": "Speaker 1: [text]\nSpeaker 2: [text]...".
  "language": "detected_language".
  "segments": [
    {
      "start_time": 0.5,
      "end_time": 2.3,
      "speaker": "Speaker 1",
      "text": "Hello everyone, let's discuss...".
      "confidence": 0.95
    }
  ],
  "confidence_score": 0.98
}

Focus on accuracy and speaker differentiation. If speakers are too similar to distinguish, use "Unknown Speaker".
"""

    def _parse_gemini_response(self, response_text: str) -> dict:
        """Parse Gemini's response into structured transcript data."""

        try:
            # Try to parse JSON directly
            parsed = json.loads(response_text)
            return parsed
        except json.JSONDecodeError:
            # If not valid JSON, try to extract JSON from response
            try:
                # Find JSON-like content in the response
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_content = response_text[start_idx:end_idx + 1]
                    return json.loads(json_content)
            except (json.JSONDecodeError, ValueError):
                pass

            # Fallback: return basic structure with raw text
            return {
                "raw_text": response_text,
                "formatted_text": response_text,
                "language": "en",
                "segments": [],
                "confidence_score": None
            }

    async def _prepare_audio_file(self, audio_path: str) -> str:
        """Prepare audio file for Gemini processing.

        Converts to appropriate format if needed. Returns path to processed file.
        """
        # For Gemini 1.5 Pro, we can usually use most common formats
        # This is a placeholder - implement specific conversion if needed
        return audio_path
async def get_speech_to_text_processor() -> SpeechToTextProcessor:
    """Factory function to get the appropriate STT processor based on configuration."""

    # If Gemini API key is configured, use Gemini processor
    if settings.GEMINI_API_KEY:
        try:
            return GeminiSTTProcessor()
        except (ImportError, ValueError) as e:
            logger.warning(f"Gemini processor not available ({e}), will fall back to Whisper")

    # Fallback to Whisper processor if Gemini not available
    try:
        from backend.app.services.whisper_processor import WhisperSTTProcessor
        return WhisperSTTProcessor()
    except ImportError as e:
        logger.error(f"No STT processor available: {e}")
        raise RuntimeError("No speech-to-text processor available. Please configure Gemini API key or install Whisper.")
class STTService:
    """Main STT service that orchestrates the processing workflow."""

    def __init__(self, db_session: SessionLocal):
        self.db = db_session
        self.processor = get_speech_to_text_processor()

    async def process_meeting_audio(self, meeting_id: str) -> TranscriptResult:
        """Process a meeting's audio file and store the transcript."""

        # Get meeting details
        meeting = self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} not found")

        # Get the uploaded audio files for this meeting
        meeting_files = meeting.files
        audio_files = [f for f in meeting_files if f.file_type in ['audio', 'video']]

        if not audio_files:
            raise ValueError(f"No audio/video files found for meeting {meeting_id}")

        # Process the first audio file (or handle multiple files as needed)
        audio_file = audio_files[0]

        # Get storage backend to access the file
        from app.services.storage import get_storage_backend
        storage = get_storage_backend()

        # Note: In a real implementation, we would stream the file directly
        # to the processor to avoid downloading large files to disk first
        # This is a simplified version

        try:
            # Process the audio file
            transcript = await self.processor.process_upload_file(
                type('UploadFile', (), {
                    'filename': audio_file.original_filename,
                    'read': lambda: b''  # Would be actual file read
                })(),
                meeting_id
            )

            # Store transcript in database
            await self._store_transcript(meeting_id, transcript)

            # Update participants with speaker identification
            await self._update_participant_speakers(meeting_id, transcript.segments)

            # Update meeting status to transcribed
            meeting.status = 'transcribed'
            self.db.commit()

            return transcript

        except Exception as e:
            logger.error(f"Failed to process audio for meeting {meeting_id}: {e}")
            raise

    async def _store_transcript(self, meeting_id: str, transcript: TranscriptResult):
        """Store transcript in database. Currently stores in memory for now."""

        # For now, we'll store the transcript in memory since we don't have a
        # transcript model. In a full implementation, we would:
        # 1. Create a MeetingTranscript model
        # 2. Save the transcript data
        # 3. Allow frontend to retrieve and display the transcript

        # Store transcript segments for easy access
        self.meeting_transcripts[meeting_id] = transcript
        logger.info(f"Stored transcript for meeting {meeting_id}")

    async def _update_participant_speakers(
        self,
        meeting_id: str,
        segments: List[TranscriptSegment]
    ):
        """Update participants with speaker labels identified in transcript."""

        # Extract unique speaker IDs from transcript segments
        speaker_ids = set()
        for segment in segments:
            if segment.speaker_id:
                speaker_ids.add(segment.speaker_id)

        # Find matching participants based on speaker IDs
        # This is a simplified version - in reality, we would have more sophisticated
        # matching logic using participant emails, names, etc.

        for participant in self.meeting.participants:
            # Simple mapping: map first few speakers to participants
            if participant.id == 'participant_1' and 'Speaker 1' in segments[0].speaker_id:
                participant.speaker_label = segment.speaker_id
            elif participant.id == 'participant_2' and 'Speaker 2' in segments[1].speaker_id:
                participant.speaker_label = segment.speaker_id

    def get_transcript(self, meeting_id: str) -> Optional[TranscriptResult]:
        """Retrieve transcript for a meeting."""

        return self.meeting_transcripts.get(meeting_id)