from app.db.database import SessionLocal
from app.services.decisions_service import extract_decisions


db = SessionLocal()

try:
    result = extract_decisions(
        db=db,
        meeting_id=3,
    )

    print("\n===== DECISIONS =====\n")
    print(result)

finally:
    db.close()