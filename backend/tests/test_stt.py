"""
Test suite for Speech-to-Text and Speaker Diarization module.
Run with: pytest backend/tests/test_stt.py -v
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

import pytest

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment before imports
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_stt.db")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("PIPELINE_SERVICE_KEY", "test-service-key")


class TestSTTServiceImports:
    """Test that all STT modules can be imported correctly."""

    def test_import_speech_to_text_service(self):
        """Test main STT service interface imports."""
        from app.services.speech_to_text import (
            SpeechToTextProcessor,
            TranscriptSegment,
            TranscriptResult,
            get_speech_to_text_processor,
            STTService,
        )
        assert SpeechToTextProcessor is not None
        assert TranscriptSegment is not None
        assert TranscriptResult is not None

    def test_import_gemini_processor(self):
        """Test Gemini processor imports."""
        from app.services.processors.gemini_processor import GeminiSTTProcessor
        assert GeminiSTTProcessor is not None

    def test_import_whisper_processor(self):
        """Test Whisper processor imports."""
        from app.services.processors.whisper_processor import WhisperSTTProcessor
        assert WhisperSTTProcessor is not None

    def test_import_stt_pipeline(self):
        """Test STT pipeline imports."""
        from app.services.stt_pipeline import STTPipeline, SpeakerMapping
        assert STTPipeline is not None
        assert SpeakerMapping is not None

    def test_import_stt_models(self):
        """Test STT database models imports."""
        from app.db.models_stt import (
            MeetingTranscript,
            TranscriptSegment as DBTranscriptSegment,
            SpeakerDiarization,
        )
        assert MeetingTranscript is not None
        assert DBTranscriptSegment is not None
        assert SpeakerDiarization is not None

    def test_import_stt_schemas(self):
        """Test STT Pydantic schemas imports."""
        from app.schemas.stt import (
            TranscriptSegmentSchema,
            SpeakerMappingSchema,
            STTProcessingResponse,
            TranscriptResponse,
        )
        assert TranscriptSegmentSchema is not None
        assert STTProcessingResponse is not None

    def test_import_stt_routes(self):
        """Test STT API routes import."""
        from app.api.routes.stt import router
        assert router is not None


class TestTranscriptSegment:
    """Test TranscriptSegment dataclass."""

    def test_create_segment(self):
        """Test creating a transcript segment."""
        from app.services.speech_to_text import TranscriptSegment

        segment = TranscriptSegment(
            start_time=0.0,
            end_time=5.5,
            speaker="Speaker 1",
            text="Hello, how are you?",
            confidence=0.95,
            speaker_id="participant-123",
        )

        assert segment.start_time == 0.0
        assert segment.end_time == 5.5
        assert segment.speaker == "Speaker 1"
        assert segment.text == "Hello, how are you?"
        assert segment.confidence == 0.95
        assert segment.speaker_id == "participant-123"

    def test_segment_defaults(self):
        """Test segment default values."""
        from app.services.speech_to_text import TranscriptSegment

        segment = TranscriptSegment(
            start_time=0.0,
            end_time=3.0,
            speaker="Speaker 2",
            text="Test text",
        )

        assert segment.confidence == 1.0
        assert segment.speaker_id is None


class TestTranscriptResult:
    """Test TranscriptResult dataclass."""

    def test_create_result(self):
        """Test creating a transcript result."""
        from app.services.speech_to_text import TranscriptSegment, TranscriptResult

        segments = [
            TranscriptSegment(
                start_time=0.0,
                end_time=3.0,
                speaker="Speaker 1",
                text="First speaker",
            ),
            TranscriptSegment(
                start_time=3.0,
                end_time=6.0,
                speaker="Speaker 2",
                text="Second speaker",
            ),
        ]

        result = TranscriptResult(
            meeting_id="test-meeting-123",
            raw_text="First speaker. Second speaker.",
            formatted_text="Speaker 1: First speaker\nSpeaker 2: Second speaker",
            language="en",
            segments=segments,
            confidence_score=0.92,
            processing_time_seconds=5,
            model_used="gemini",
        )

        assert result.meeting_id == "test-meeting-123"
        assert len(result.segments) == 2
        assert result.language == "en"
        assert result.confidence_score == 0.92
        assert result.model_used == "gemini"

    def test_result_default_values(self):
        """Test result default values."""
        from app.services.speech_to_text import TranscriptResult

        result = TranscriptResult(
            meeting_id="test-123",
            raw_text="Test",
            formatted_text="Test",
        )

        assert result.language == "en"
        assert result.segments == []
        assert result.confidence_score is None
        assert result.processing_time_seconds == 0
        assert result.model_used == "gemini"


class TestGeminiProcessor:
    """Test Gemini STT Processor."""

    def test_gemini_processor_initialization(self):
        """Test Gemini processor can be initialized."""
        from app.services.processors.gemini_processor import GeminiSTTProcessor

        # Mock the google.generativeai module
        with patch("google.generativeai.configure") as mock_configure:
            processor = GeminiSTTProcessor()
            assert processor is not None

    @pytest.mark.asyncio
    async def test_gemini_process_audio_returns_result(self):
        """Test Gemini processor returns a result."""
        from app.services.processors.gemini_processor import GeminiSTTProcessor

        with patch("google.generativeai.configure"):
            processor = GeminiSTTProcessor()

            # Create a temp audio file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(b"fake audio data")
                temp_path = f.name

            try:
                result = await processor.process_audio(
                    temp_path,
                    "test-meeting-123",
                    "test-audio.mp3",
                )

                assert result is not None
                assert result.meeting_id == "test-meeting-123"
                assert isinstance(result.raw_text, str)
                assert isinstance(result.formatted_text, str)
                assert result.model_used == "gemini"
            finally:
                os.unlink(temp_path)


class TestWhisperProcessor:
    """Test Whisper STT Processor."""

    def test_whisper_processor_initialization(self):
        """Test Whisper processor can be initialized without loading models."""
        from app.services.processors.whisper_processor import WhisperSTTProcessor

        # Initialize with model loading disabled for test
        processor = WhisperSTTProcessor.__new__(WhisperSTTProcessor)
        processor.model_size = "base"
        processor.device = "cpu"
        processor.whisper_model = None
        processor.diarization_pipeline = None

        assert processor.model_size == "base"
        assert processor.device == "cpu"
        assert processor.whisper_model is None


class TestSpeakerMapping:
    """Test SpeakerMapping dataclass."""

    def test_create_speaker_mapping(self):
        """Test creating a speaker mapping."""
        from app.services.stt_pipeline import SpeakerMapping

        mapping = SpeakerMapping(
            diarizer_speaker="Speaker 1",
            participant_id="participant-123",
            participant_name="John Doe",
            confidence=0.85,
        )

        assert mapping.diarizer_speaker == "Speaker 1"
        assert mapping.participant_id == "participant-123"
        assert mapping.participant_name == "John Doe"
        assert mapping.confidence == 0.85

    def test_speaker_mapping_no_participant(self):
        """Test speaker mapping when no participant matched."""
        from app.services.stt_pipeline import SpeakerMapping

        mapping = SpeakerMapping(
            diarizer_speaker="Speaker 3",
            participant_id=None,
            participant_name=None,
            confidence=0.5,
        )

        assert mapping.participant_id is None
        assert mapping.participant_name is None
        assert mapping.confidence == 0.5


class TestSTTSchemas:
    """Test Pydantic schemas for STT."""

    def test_transcript_segment_schema(self):
        """Test TranscriptSegmentSchema validation."""
        from app.schemas.stt import TranscriptSegmentSchema

        schema = TranscriptSegmentSchema(
            start_time=0.0,
            end_time=5.5,
            speaker="Speaker 1",
            text="Test transcript",
            confidence=0.95,
        )

        assert schema.start_time == 0.0
        assert schema.end_time == 5.5
        assert schema.speaker == "Speaker 1"
        assert schema.text == "Test transcript"
        assert schema.confidence == 0.95

    def test_speaker_mapping_schema(self):
        """Test SpeakerMappingSchema validation."""
        from app.schemas.stt import SpeakerMappingSchema

        schema = SpeakerMappingSchema(
            diarizer_speaker="Speaker 1",
            participant_id="participant-123",
            confidence=0.85,
        )

        assert schema.diarizer_speaker == "Speaker 1"
        assert schema.participant_id == "participant-123"

    def test_stt_processing_response(self):
        """Test STTProcessingResponse schema."""
        from app.schemas.stt import STTProcessingResponse, TranscriptSegmentSchema

        response = STTProcessingResponse(
            meeting_id="test-123",
            status="success",
            raw_text="Raw transcript text",
            formatted_text="Speaker 1: Raw transcript text",
            segments=[
                TranscriptSegmentSchema(
                    start_time=0.0,
                    end_time=3.0,
                    speaker="Speaker 1",
                    text="Raw transcript text",
                )
            ],
            processing_time_seconds=5,
            transcriber_model="gemini",
        )

        assert response.meeting_id == "test-123"
        assert response.status == "success"
        assert len(response.segments) == 1


class TestSTTDatabaseModels:
    """Test STT database models."""

    def test_meeting_transcript_model(self):
        """Test MeetingTranscript model fields."""
        from app.db.models_stt import MeetingTranscript

        transcript = MeetingTranscript(
            meeting_id="test-meeting-123",
            raw_text="Test raw transcript",
            formatted_text="Speaker 1: Test raw transcript",
            language="en",
            duration_seconds=120.5,
            overall_confidence=0.92,
            transcriber_model="gemini",
        )

        assert transcript.meeting_id == "test-meeting-123"
        assert transcript.raw_text == "Test raw transcript"
        assert transcript.formatted_text == "Speaker 1: Test raw transcript"
        assert transcript.language == "en"
        assert transcript.duration_seconds == 120.5

    def test_transcript_segment_model(self):
        """Test TranscriptSegment model fields."""
        from app.db.models_stt import TranscriptSegment

        segment = TranscriptSegment(
            transcript_id="transcript-123",
            start_time=0.0,
            end_time=5.5,
            speaker_label="Speaker 1",
            speaker_id="participant-123",
            text="Hello world",
            confidence=0.95,
        )

        assert segment.transcript_id == "transcript-123"
        assert segment.start_time == 0.0
        assert segment.end_time == 5.5
        assert segment.speaker_label == "Speaker 1"
        assert segment.text == "Hello world"

    def test_speaker_diarization_model(self):
        """Test SpeakerDiarization model fields."""
        from app.db.models_stt import SpeakerDiarization

        diarization = SpeakerDiarization(
            meeting_id="meeting-123",
            diarizer_speaker="Speaker 1",
            participant_id="participant-123",
            confidence=0.85,
            first_appearance=0.0,
            last_appearance=30.5,
        )

        assert diarization.meeting_id == "meeting-123"
        assert diarization.diarizer_speaker == "Speaker 1"
        assert diarization.confidence == 0.85


class TestConfigSettings:
    """Test STT configuration settings."""

    def test_stt_config_loaded(self):
        """Test STT configuration is available."""
        from app.core.config import settings

        # Check STT-related settings exist
        assert hasattr(settings, "GEMINI_API_KEY")
        assert hasattr(settings, "STT_MODEL_PROVIDER")
        assert hasattr(settings, "WHISPER_MODEL_SIZE")
        assert hasattr(settings, "HUGGINGFACE_TOKEN")
        assert hasattr(settings, "PIPELINE_SERVICE_KEY")

    def test_default_model_provider(self):
        """Test default STT model provider."""
        from app.core.config import settings

        assert settings.STT_MODEL_PROVIDER in ["gemini", "whisper"]


class TestAPIRoutes:
    """Test STT API routes."""

    def test_stt_router_exists(self):
        """Test STT router is properly configured."""
        from app.api.routes.stt import router

        assert router is not None
        # Check routes are registered
        routes = [r.path for r in router.routes]
        assert any("process-stt" in path for path in routes)
        assert any("transcript" in path for path in routes)
        assert any("speaker-mapping" in path for path in routes)

    def test_service_key_verification(self):
        """Test service key verification function."""
        from app.api.routes.stt import verify_service_key
        from fastapi import HTTPException

        # Valid key should not raise
        try:
            verify_service_key("test-service-key")
        except HTTPException:
            pytest.fail("Valid service key raised HTTPException")

        # Invalid key should raise
        with pytest.raises(HTTPException) as exc_info:
            verify_service_key("wrong-key")
        assert exc_info.value.status_code == 401


class TestIntegration:
    """Integration tests for STT workflow."""

    @pytest.mark.asyncio
    async def test_full_transcript_workflow(self):
        """Test complete transcript creation workflow."""
        from app.services.speech_to_text import TranscriptSegment, TranscriptResult

        # Simulate processing workflow
        segments = [
            TranscriptSegment(
                start_time=0.0,
                end_time=2.5,
                speaker="Speaker 1",
                text="Hello everyone, welcome to the meeting.",
                confidence=0.98,
            ),
            TranscriptSegment(
                start_time=2.5,
                end_time=5.0,
                speaker="Speaker 2",
                text="Thank you. Let's get started.",
                confidence=0.95,
            ),
            TranscriptSegment(
                start_time=5.0,
                end_time=8.5,
                speaker="Speaker 1",
                text="Today we will discuss the quarterly results.",
                confidence=0.97,
            ),
        ]

        raw_text = " ".join([s.text for s in segments])
        formatted_text = "\n".join([f"{s.speaker}: {s.text}" for s in segments])

        result = TranscriptResult(
            meeting_id="integration-test-123",
            raw_text=raw_text,
            formatted_text=formatted_text,
            segments=segments,
            confidence_score=0.97,
            processing_time_seconds=3,
        )

        # Verify result
        assert len(result.segments) == 3
        assert result.segments[0].speaker == "Speaker 1"
        assert result.segments[1].speaker == "Speaker 2"
        assert "Hello everyone" in result.raw_text
        assert "Speaker 1: Hello everyone" in result.formatted_text
        assert result.confidence_score == 0.97

    def test_speaker_identification_consistency(self):
        """Test that speaker identification is consistent across segments."""
        from app.services.speech_to_text import TranscriptSegment

        segments = [
            TranscriptSegment(start_time=0.0, end_time=2.0, speaker="Speaker 1", text="Hello"),
            TranscriptSegment(start_time=2.0, end_time=4.0, speaker="Speaker 2", text="Hi there"),
            TranscriptSegment(start_time=4.0, end_time=6.0, speaker="Speaker 1", text="How are you?"),
            TranscriptSegment(start_time=6.0, end_time=8.0, speaker="Speaker 2", text="I'm good"),
        ]

        # Count speaker appearances
        speaker_1_count = sum(1 for s in segments if s.speaker == "Speaker 1")
        speaker_2_count = sum(1 for s in segments if s.speaker == "Speaker 2")

        assert speaker_1_count == 2
        assert speaker_2_count == 2

        # Verify alternating pattern
        expected_speakers = ["Speaker 1", "Speaker 2", "Speaker 1", "Speaker 2"]
        for i, segment in enumerate(segments):
            assert segment.speaker == expected_speakers[i]


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "asyncio: mark test as async")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
