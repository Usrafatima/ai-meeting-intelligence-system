
from sqlalchemy.orm import Session
from google import genai

from app.core.config import settings
from app.services.vector_search import search_similar_transcripts


client = genai.Client(api_key=settings.GEMINI_API_KEY)


def answer_question(
    db: Session,
    meeting_id: int,
    question: str,
    top_k: int = 5,
) -> str:

    results = search_similar_transcripts(
        db=db,
        query=question,
        meeting_id=meeting_id,
        top_k=top_k,
    )

    if not results:
        return "I could not find relevant information in this meeting transcript."

    context_parts = []

    for chunk, distance in results:
        context_parts.append(
            f"Transcript:\n{chunk.content}"
        )

    context = "\n\n".join(context_parts)

    prompt = f"""
You are an AI meeting assistant.

Answer the user's question using ONLY the meeting transcript context provided below.

If the answer cannot be found in the context, say:
"I could not find that information in the meeting transcript."

Meeting transcript context:
{context}

User question:
{question}

Answer clearly and concisely.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text
