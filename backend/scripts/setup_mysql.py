"""
Create MySQL database tables and optionally copy old SQLite / feedback.json data.

Usage (from backend folder):
  pip install pymysql
  set MYSQL_* in .env first
  python scripts/setup_mysql.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from modules.contact.storage import import_feedback_json_to_db
from modules.questionbank.db import IS_MYSQL, SessionLocal, database_info, init_db
from modules.questionbank.models import (
    ActivityLog,
    Board,
    Book,
    Chapter,
    ContactFeedback,
    ExamType,
    PaperPattern,
    Question,
    SavedPaper,
    SchoolClass,
    Subject,
    User,
)
from modules.questionbank.seed import run_seed


def copy_sqlite_if_exists():
    sqlite_path = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")),
        "questionbank.db",
    )
    if not os.path.isfile(sqlite_path):
        print("No SQLite file to migrate:", sqlite_path)
        return

    import sqlite3

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    from modules.questionbank.db import get_database_url

    dst_engine = create_engine(get_database_url(), pool_pre_ping=True)
    Dst = sessionmaker(bind=dst_engine)

    tables_order = [
        ("boards", Board, ["id", "name", "code", "created_at"]),
        ("exam_types", ExamType, ["id", "name", "code", "created_at"]),
        ("subjects", Subject, ["id", "name", "created_at"]),
        ("classes", SchoolClass, ["id", "name", "board_id", "created_at"]),
        ("school_classes", SchoolClass, ["id", "name", "board_id", "created_at"]),
        ("books", Book, ["id", "subject_id", "name", "created_at"]),
        ("chapters", Chapter, ["id", "book_id", "title", "content_text", "sort_order", "created_at"]),
        ("paper_patterns", PaperPattern, ["id", "board_id", "exam_type_id", "mcq_count", "short_count", "long_count", "total_marks", "duration", "created_at"]),
        ("questions", Question, ["id", "chapter_id", "question_type", "question_text", "options_json", "correct_answer", "difficulty", "source", "created_at"]),
        ("users", User, ["id", "name", "email", "password_hash", "role", "created_at"]),
        ("saved_papers", SavedPaper, ["id", "title", "payload_json", "filters_json", "created_at"]),
    ]

    db = Dst()
    try:
        for table_name, model, _cols in tables_order:
            try:
                existing = db.query(model).count()
            except Exception:
                continue
            if existing:
                print(f"Skip {table_name} — already has rows")
                continue
            try:
                rows = src.execute(f"SELECT * FROM {table_name}").fetchall()
            except sqlite3.OperationalError:
                continue
            if not rows:
                continue
            for r in rows:
                data = dict(r)
                if table_name == "saved_papers":
                    data.setdefault("user_id", None)
                    data.setdefault("module", "questionbank")
                    data.setdefault("mode", "")
                db.add(model(**data))
            db.commit()
            print(f"Migrated {len(rows)} rows from {table_name}")
    finally:
        db.close()
        src.close()


def main():
    if not IS_MYSQL:
        print("MySQL not configured. Add to backend/.env:")
        print("  MYSQL_HOST=localhost")
        print("  MYSQL_PORT=3306")
        print("  MYSQL_USER=your_user")
        print("  MYSQL_PASSWORD=your_password")
        print("  MYSQL_DATABASE=quick_study_db")
        print("Or: DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/quick_study_db")
        sys.exit(1)

    print("Database:", database_info())
    init_db()
    run_seed()
    imported = import_feedback_json_to_db()
    if imported:
        print(f"Imported {imported} contact messages from feedback.json")
    copy_sqlite_if_exists()

    db = SessionLocal()
    try:
        print("Tables ready:")
        for label, model in [
            ("users", User),
            ("boards", Board),
            ("questions", Question),
            ("saved_papers", SavedPaper),
            ("contact_feedback", ContactFeedback),
            ("activity_logs", ActivityLog),
        ]:
            print(f"  {label}: {db.query(model).count()} rows")
    finally:
        db.close()
    print("Done.")


if __name__ == "__main__":
    main()
