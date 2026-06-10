import json

from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import ActivityLog


def try_log(module, action, details=None, user_id=None):
    try:
        init_db()
        db = SessionLocal()
        try:
            row = ActivityLog(
                user_id=user_id,
                module=(module or "unknown")[:40],
                action=(action or "action")[:80],
                details_json=json.dumps(details or {}),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row.id
        finally:
            db.close()
    except Exception:
        return None
