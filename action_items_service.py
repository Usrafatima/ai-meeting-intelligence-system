from sqlalchemy.orm import Session
from google import genai

from app.core.config import settings
from app.db.models import TranscriptChunk


client = genai.Client(api_key=settings.GEMINI_API_KEY)


def extract_action_items(
    db: Session,
    meeting_id: str,
) -> str:

    # Get meeting transcript
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

Analyze the following meeting transcript and extract all action items.

For each action item, identify:

- Task
- Person responsible, if mentioned
- Deadline, if mentioned

If the person or deadline is not mentioned, write "Not specified".

Return the result in clear, simple JSON format:

{{
  "action_items": [
    {{
      "task": "string",
      "assignee": "string",
      "deadline": "string"
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