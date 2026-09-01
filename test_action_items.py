from app.db.database import SessionLocal
from app.services.action_items_service import extract_action_items


db = SessionLocal()

try:
    result = extract_action_items(
        db=db,
        meeting_id=3,
    )

    print("\n===== ACTION ITEMS =====\n")
    print(result)

finally:
    db.close()