"""
Create the first admin user in MySQL/SQLite.

Usage (from backend folder):
  python scripts/create_admin.py
  python scripts/create_admin.py --email admin@qsb.com --password Admin123 --name "Site Admin"
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

from modules.questionbank.db import SessionLocal, database_info, init_db
from modules.questionbank.models import User


def main():
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--email", default="admin@quickstudy.com")
    parser.add_argument("--password", default="Admin123")
    parser.add_argument("--name", default="Admin")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        email = args.email.strip().lower()
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            existing.role = "admin"
            existing.password_hash = generate_password_hash(args.password)
            existing.name = args.name
            db.commit()
            print(f"Updated existing user to admin: {email}")
        else:
            db.add(
                User(
                    name=args.name,
                    email=email,
                    password_hash=generate_password_hash(args.password),
                    role="admin",
                )
            )
            db.commit()
            print(f"Admin created: {email}")
        print("Database:", database_info())
        print("Login at: http://localhost:5500/login.html")
        print("Password:", args.password)
    finally:
        db.close()


if __name__ == "__main__":
    main()
