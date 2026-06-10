"""
Create the website admin user (one-time).

Usage:
  cd backend
  python create_admin.py

Admin panel URL (after login):
  http://127.0.0.1:5500/module/questionbank/admin.html
"""
import getpass

from werkzeug.security import generate_password_hash

from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import User


def main():
    init_db()
    print("=== Quick Study Builder — Create Admin ===\n")

    name = input("Admin name [Site Admin]: ").strip() or "Site Admin"
    email = input("Admin email: ").strip().lower()
    if not email:
        print("Email required.")
        return

    password = getpass.getpass("Admin password (min 6 chars): ")
    if len(password) < 6:
        print("Password too short.")
        return

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role != "admin":
                print(f"Email already used as {existing.role}. Use another email.")
                return
            existing.name = name
            existing.password_hash = generate_password_hash(password)
            db.commit()
            print(f"\nUpdated admin: {email}")
        else:
            db.add(
                User(
                    name=name,
                    email=email,
                    password_hash=generate_password_hash(password),
                    role="admin",
                )
            )
            db.commit()
            print(f"\nAdmin created: {email}")
        print("\nLogin at: login.html")
        print("Then open: module/questionbank/admin.html")
    finally:
        db.close()


if __name__ == "__main__":
    main()
