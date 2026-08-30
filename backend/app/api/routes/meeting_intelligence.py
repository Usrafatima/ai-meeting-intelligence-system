"""
AI Meeting Intelligence routes.
Analyzes a meeting transcript and returns summary, decisions, action items, sentiment.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.meeting_intelligence import AnalyzeMeetingRequest, MeetingIntelligenceResponse
from app.services.processors.gemini_intelligence_processor import GeminiMeetingIntelligenceProcessor

router = APIRouter()


@router.post("/{meeting_id}/analyze", response_model=MeetingIntelligenceResponse)
async def analyze_meeting(meeting_id: str, request: AnalyzeMeetingRequest):
    if meeting_id != request.meeting_id:
        raise HTTPException(status_code=400, detail="meeting_id in path and body must match")

    if not request.transcript:
        raise HTTPException(status_code=400, detail="transcript cannot be empty")

    try:
        processor = GeminiMeetingIntelligenceProcessor()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    segments = [seg.model_dump() for seg in request.transcript]

    try:
        result = await processor.analyze(meeting_id, segments, request.summary_mode)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meeting intelligence analysis failed: {e}")

    try:
        return MeetingIntelligenceResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model output didn't match expected schema: {e}")

    # TODO: persist result to DB (decisions, action_items, deadlines tables) once
    # app/db/models.py has tables for these — ask teammates if that's already planned.