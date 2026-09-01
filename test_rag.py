from app.db.database import SessionLocal
from app.services.rag_service import answer_question


db = SessionLocal()

try:
    question = "What did we discuss about RAG?"

    answer = answer_question(
        db=db,
        meeting_id=3,
        question=question,
    )

    print("\nQuestion:")
    print(question)

    print("\nAnswer:")
    print(answer)

finally:
    db.close()