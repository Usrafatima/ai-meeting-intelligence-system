
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import TranscriptChunk
from app.services.embedding_service import generate_embedding


def search_similar_transcripts(
    db: Session,
    query: str,
    meeting_id: int,
    top_k: int = 5,
):
    """
    Search transcript chunks using pgvector cosine similarity.

    Only transcript chunks belonging to the requested meeting
    are searched.
    """

    query_embedding = generate_embedding(query)

    distance = TranscriptChunk.embedding.cosine_distance(
        query_embedding
    )

    statement = (
        select(
            TranscriptChunk,
            distance.label("distance"),
        )
        .where(
            TranscriptChunk.meeting_id == meeting_id,
            TranscriptChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(top_k)
    )

    results = db.execute(statement).all()

    return results

