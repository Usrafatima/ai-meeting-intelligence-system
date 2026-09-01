from app.db.database import SessionLocal
from app.services.vector_search import search_similar_transcripts


db = SessionLocal()

try:
    results = search_similar_transcripts(
        db=db,
        query="What did we discuss about RAG?",
        meeting_id=3,
        top_k=5,
    )

    print(f"Found {len(results)} result(s).")

    for chunk, distance in results:
        print("\n--- Result ---")
        print("Transcript ID:", chunk.id)
        print("Meeting ID:", chunk.meeting_id)
        print("Distance:", distance)
        print("Content:", chunk.content)

finally:
    db.close()