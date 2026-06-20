import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FEEDBACK_FILE = DATA_DIR / "feedback.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _use_database():
    try:
        from modules.questionbank.db import IS_MYSQL, init_db

        if not IS_MYSQL:
            return False
        init_db()
        return True
    except Exception:
        return False


def _feedback_to_dict(row):
    return {
        "id": row.id,
        "name": row.name,
        "email": row.email,
        "subject": row.subject,
        "message": row.message,
        "rating": row.rating,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def load_feedback():
    if _use_database():
        from modules.questionbank.db import SessionLocal
        from modules.questionbank.models import ContactFeedback

        db = SessionLocal()
        try:
            rows = (
                db.query(ContactFeedback)
                .order_by(ContactFeedback.id.desc())
                .all()
            )
            return [_feedback_to_dict(r) for r in reversed(rows)]
        finally:
            db.close()

    _ensure_data_dir()
    if not FEEDBACK_FILE.exists():
        return []
    try:
        with open(FEEDBACK_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_feedback_entry(entry: dict) -> dict:
    if _use_database():
        from modules.questionbank.db import SessionLocal
        from modules.questionbank.models import ContactFeedback

        db = SessionLocal()
        try:
            row = ContactFeedback(
                name=entry.get("name") or "Anonymous",
                email=entry.get("email") or "",
                subject=entry.get("subject") or "feedback",
                message=entry.get("message") or "",
                rating=entry.get("rating"),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _feedback_to_dict(row)
        finally:
            db.close()

    _ensure_data_dir()
    rows = load_feedback()
    entry = {
        **entry,
        "id": len(rows) + 1,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    rows.append(entry)
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    return entry


def import_feedback_json_to_db():
    """One-time: copy feedback.json rows into MySQL/SQLite contact_feedback table."""
    if not FEEDBACK_FILE.exists():
        return 0
    if not _use_database():
        return 0

    from modules.questionbank.db import SessionLocal
    from modules.questionbank.models import ContactFeedback

    try:
        with open(FEEDBACK_FILE, encoding="utf-8") as f:
            rows = json.load(f)
    except (json.JSONDecodeError, OSError):
        return 0

    db = SessionLocal()
    imported = 0
    try:
        existing = db.query(ContactFeedback).count()
        if existing:
            return 0
        for item in rows:
            db.add(
                ContactFeedback(
                    name=item.get("name") or "Anonymous",
                    email=item.get("email") or "",
                    subject=item.get("subject") or "feedback",
                    message=item.get("message") or "",
                    rating=item.get("rating"),
                )
            )
            imported += 1
        db.commit()
    finally:
        db.close()
    return imported


def get_contact_email():
    env = (os.getenv("CONTACT_EMAIL") or "").strip()
    if env:
        return env
    try:
        from modules.questionbank.db import SessionLocal, init_db
        from modules.questionbank.models import User

        init_db()
        db = SessionLocal()
        try:
            admin = (
                db.query(User)
                .filter(User.role == "admin")
                .order_by(User.id.asc())
                .first()
            )
            if admin and admin.email:
                return admin.email.strip()
        finally:
            db.close()
    except Exception:
        pass
    return "admin@gmail.com"
