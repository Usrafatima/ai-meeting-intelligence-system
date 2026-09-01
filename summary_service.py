from sqlalchemy.orm import Session
from google import genai

from app.core.config import settings
from app.db.models import TranscriptChunk


client = genai.Client(api_key=settings.GEMINI_API_KEY)


def generate_meeting_summary(
    db: Session,
    meeting_id: str,
) -> str:

    chunks = (
        db.query(TranscriptChunk)
        .filter(TranscriptChunk.meeting_id == meeting_id)
        .order_by(TranscriptChunk.id)
        .all()
    )

    if not chunks:
        return "No transcript available for this meeting."

    transcript = "\n\n".join(
        chunk.content
        for chunk in chunks
    )

    prompt = f"""
You are an AI meeting assistant.

Create a clear and concise summary of the following meeting transcript.

Include:
- Main topics discussed
- Important points
- Decisions made
- Overall outcome

Meeting transcript:

{transcript}

Write the summary in simple, professional language.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text