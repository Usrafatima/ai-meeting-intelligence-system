from sqlalchemy.orm import Session
from google import genai

from app.core.config import settings
from app.db.models import TranscriptChunk


client = genai.Client(api_key=settings.GEMINI_API_KEY)


def extract_decisions(
    db: Session,
    meeting_id: int,
) -> str:

    chunks = (
        db.query(TranscriptChunk)
        .filter(
            TranscriptChunk.meeting_id == meeting_id
        )
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

Analyze the following meeting transcript and identify the
important decisions made during the meeting.

For each decision, identify:

- Decision
- Reason, if mentioned
- Person/team responsible, if mentioned

If the reason or responsible person is not mentioned,
write "Not specified".

Return the result in clear JSON format:

{{
  "decisions": [
    {{
      "decision": "string",
      "reason": "string",
      "responsible": "string"
    }}
  ]
}}

Do not invent information.

Meeting transcript:

{transcript}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text