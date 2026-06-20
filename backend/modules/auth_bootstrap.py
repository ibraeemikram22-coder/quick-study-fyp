import os

from werkzeug.security import generate_password_hash

from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import User


def ensure_admin_user():
    """Create or update admin from .env so login always works after backend start."""
    email = (os.getenv("ADMIN_EMAIL") or "admin@gmail.com").strip().lower()
    password = os.getenv("ADMIN_PASSWORD") or "admin123"
    name = (os.getenv("ADMIN_NAME") or "Site Admin").strip()

    if not email or len(password) < 6:
        return

    init_db()
    db = SessionLocal()
    try:
        row = db.query(User).filter(User.email == email).first()
        pwd_hash = generate_password_hash(password)
        if row:
            if row.role != "admin":
                row.role = "admin"
            row.name = name
            row.password_hash = pwd_hash
            row.is_verified = 1
        else:
            db.add(
                User(
                    name=name,
                    email=email,
                    password_hash=pwd_hash,
                    role="admin",
                    is_verified=1,
                )
            )
        db.commit()
    finally:
        db.close()
