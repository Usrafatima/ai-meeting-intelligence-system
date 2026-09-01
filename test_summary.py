from app.db.database import SessionLocal
from app.services.summary_service import generate_meeting_summary


db = SessionLocal()

try:
    summary = generate_meeting_summary(
        db=db,
        meeting_id=3,
    )

    print("\n===== MEETING SUMMARY =====\n")
    print(summary)

finally:
    db.close()