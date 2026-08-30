"""
Tests for the AI Meeting Intelligence module.
Mocks the Gemini call so these run without hitting the real API.
Run with: python -m pytest tests/test_meeting_intelligence.py -v
"""
import sys
import os
import json
import asyncio
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.meeting_intelligence import MeetingIntelligenceResponse
from app.services.processors.gemini_intelligence_processor import GeminiMeetingIntelligenceProcessor


MOCK_JSON_RESPONSE = json.dumps({
    "summary_short": "Team agreed on launch date and assigned homepage task.",
    "summary_detailed": "The team discussed the website launch. Speaker 2 will finish the homepage by Friday. Launch date set for Sept 1. Marketing budget remains unresolved.",
    "key_points": ["Launch timing", "Homepage task"],
    "decisions": [{"decision": "Launch on September 1.", "timestamp": "0:40"}],
    "action_items": [{"task": "Finish homepage", "owner": "Speaker 2", "deadline": None, "deadline_raw": "Friday"}],
    "unresolved_issues": [{"issue": "Marketing budget", "raised_by": "Speaker 1"}],
    "follow_up_items": ["Finalize budget"],
    "sentiment": "neutral",
    "sentiment_notes": "Task-focused, one open item."
})


def test_analyze_returns_valid_schema():
    processor = GeminiMeetingIntelligenceProcessor.__new__(GeminiMeetingIntelligenceProcessor)
    fake_response = MagicMock()
    fake_response.text = MOCK_JSON_RESPONSE
    processor.model = MagicMock()
    processor.model.generate_content = MagicMock(return_value=fake_response)

    segments = [
        {"start_time": 0, "end_time": 15, "speaker": "Speaker 1", "text": "We should launch next week."},
        {"start_time": 15, "end_time": 30, "speaker": "Speaker 2", "text": "I will finish the homepage by Friday."},
    ]

    result = asyncio.run(processor.analyze("mtg_001", segments, "detailed"))
    validated = MeetingIntelligenceResponse(**result)

    assert validated.meeting_id == "mtg_001"
    assert validated.sentiment == "neutral"
    assert len(validated.action_items) == 1
    assert validated.action_items[0].owner == "Speaker 2"
    assert validated.action_items[0].deadline_raw == "Friday"
    assert len(validated.decisions) == 1
    assert "September 1" in validated.decisions[0].decision


def test_analyze_handles_malformed_json_gracefully():
    processor = GeminiMeetingIntelligenceProcessor.__new__(GeminiMeetingIntelligenceProcessor)
    fake_response = MagicMock()
    fake_response.text = "not valid json {{{"
    processor.model = MagicMock()
    processor.model.generate_content = MagicMock(return_value=fake_response)

    segments = [{"start_time": 0, "speaker": "Speaker 1", "text": "Hello."}]
    result = asyncio.run(processor.analyze("mtg_002", segments, "detailed"))

    # Should not raise — falls back to a safe default shape
    validated = MeetingIntelligenceResponse(**result)
    assert validated.meeting_id == "mtg_002"
    assert validated.sentiment == "unknown"