from app.db.database import SessionLocal
from app.db.models import TranscriptChunk
from app.services.embedding_service import generate_embedding


def generate_missing_embeddings():
    db = SessionLocal()

    try:
        chunks = (
            db.query(TranscriptChunk)
            .filter(TranscriptChunk.embedding.is_(None))
            .all()
        )

        print(f"Found {len(chunks)} transcript chunks without embeddings.")

        for chunk in chunks:
            print(f"Generating embedding for transcript ID: {chunk.id}")

            chunk.embedding = generate_embedding(chunk.content)

            print(f"Embedding saved for transcript ID: {chunk.id}")

        db.commit()

        print("All embeddings generated successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    generate_missing_embeddings()