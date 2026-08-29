import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

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
    model_used: str = "gemini"


class GeminiSTTProcessor:
    """Gemini-based speech-to-text and speaker diarization processor."""

    # Try these models in order — first available will be used
    MODEL_NAMES = [
        "gemini-3.5-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    def __init__(self):
        from app.core.config import settings
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key or self.api_key.startswith("your-"):
            raise ValueError("GEMINI_API_KEY not configured in settings")

        import google.generativeai as genai
        self.genai = genai
        self.genai.configure(api_key=self.api_key)

        # Find the first available model
        self.model = None
        for model_name in self.MODEL_NAMES:
            try:
                self.model = self.genai.GenerativeModel(model_name)
                logger.info(f"Using Gemini model: {model_name}")
                break
            except Exception as e:
                logger.warning(f"Model {model_name} not available: {e}")
                continue

        if self.model is None:
            raise ValueError("No available Gemini model found")

    async def process_audio(
        self,
        audio_path: str,
        meeting_id: str,
        filename: str
    ):
        import time
        start_time = time.time()

        logger.info(f"Processing audio with Gemini for meeting {meeting_id}: {audio_path}")

        processed_path = await self._prepare_audio_file(audio_path)

        try:
            with open(processed_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()

            prompt = self._create_transcription_prompt()

            # Try audio input first, fall back to text-based if not supported
            try:
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    [prompt, {'mime_type': 'audio/mpeg', 'data': audio_bytes}]
                )
                result = self._parse_gemini_response(response.text)
            except Exception as audio_error:
                logger.warning(f"Audio input not supported, trying base64: {audio_error}")
                import base64
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    [prompt, {'mime_type': 'audio/mpeg', 'data': audio_b64}]
                )
                result = self._parse_gemini_response(response.text)

            processing_time = time.time() - start_time

            return TranscriptResult(
                meeting_id=meeting_id,
                raw_text=result.get('raw_text', ''),
                formatted_text=result.get('formatted_text', ''),
                language=result.get('language', 'en'),
                segments=[
                    TranscriptSegment(
                        start_time=seg.get('start_time', 0.0),
                        end_time=seg.get('end_time', 0.0),
                        speaker=seg.get('speaker', 'Speaker 1'),
                        text=seg.get('text', ''),
                        confidence=seg.get('confidence', 0.9),
                        speaker_id=seg.get('speaker_id'),
                    )
                    for seg in result.get('segments', [])
                ],
                confidence_score=result.get('confidence_score'),
                processing_time_seconds=int(processing_time),
                model_used='gemini'
            )

        finally:
            Path(processed_path).unlink(missing_ok=True)

    def _create_transcription_prompt(self) -> str:
        return """
Listen to this meeting audio and transcribe it with speaker identification.

Return valid JSON in this format (no markdown, no extra text):
{
  "raw_text": "Full transcription",
  "formatted_text": "Speaker 1: text",
  "language": "en",
  "segments": [
    {"start_time": 0.0, "end_time": 5.0, "speaker": "Speaker 1", "text": "Hello everyone", "confidence": 0.95}
  ],
  "confidence_score": 0.95
}

Label speakers as Speaker 1, Speaker 2, etc. Return ONLY JSON.
"""

    def _parse_gemini_response(self, response_text: str) -> dict:
        try:
            parsed = json.loads(response_text.strip())
            return parsed
        except json.JSONDecodeError:
            try:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_content = response_text[start_idx:end_idx + 1]
                    return json.loads(json_content.strip())
            except (json.JSONDecodeError, ValueError):
                pass

            return {
                "raw_text": response_text.strip(),
                "formatted_text": response_text.strip(),
                "language": "en",
                "segments": [],
                "confidence_score": None
            }

    async def _prepare_audio_file(self, audio_path: str) -> str:
        return audio_path
