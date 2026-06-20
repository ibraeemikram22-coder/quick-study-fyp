import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "questionbank.db")


def get_database_url():
    """MySQL via DATABASE_URL or MYSQL_* env vars; otherwise local SQLite."""
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url

    user = (os.getenv("MYSQL_USER") or "").strip()
    db_name = (os.getenv("MYSQL_DATABASE") or "").strip()
    if user and db_name:
        try:
            import pymysql  # noqa: F401
        except ImportError:
            print(
                "[DB] pymysql not installed — using SQLite. "
                "Run: venv\\Scripts\\pip install pymysql"
            )
            return f"sqlite:///{DB_PATH}"
        host = (os.getenv("MYSQL_HOST") or "localhost").strip()
        port = (os.getenv("MYSQL_PORT") or "3306").strip()
        password = quote_plus(os.getenv("MYSQL_PASSWORD") or "")
        return (
            f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
            "?charset=utf8mb4"
        )

    return f"sqlite:///{DB_PATH}"


DATABASE_URL = get_database_url()
IS_MYSQL = DATABASE_URL.startswith("mysql")

_engine_kwargs = {"pool_pre_ping": True} if IS_MYSQL else {}
if not IS_MYSQL:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_user_roles():
    """Normalize NULL or mixed-case role values."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET role = 'student' WHERE role IS NULL OR TRIM(role) = ''")
        )
        for bad_role, good_role in (
            ("Student", "student"),
            ("Teacher", "teacher"),
            ("Admin", "admin"),
        ):
            conn.execute(
                text("UPDATE users SET role = :good WHERE role = :bad"),
                {"good": good_role, "bad": bad_role},
            )


def _migrate_user_columns():
    """Add verification columns on existing SQLite / MySQL DBs."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    stmts = []
    if "is_verified" not in cols:
        if IS_MYSQL:
            stmts.append("ALTER TABLE users ADD COLUMN is_verified TINYINT(1) DEFAULT 1")
        else:
            stmts.append("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 1")
    if "verify_code" not in cols:
        stmts.append("ALTER TABLE users ADD COLUMN verify_code VARCHAR(10) NULL")
    if "verify_expires" not in cols:
        stmts.append("ALTER TABLE users ADD COLUMN verify_expires DATETIME NULL")
    if not stmts:
        return
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))
        conn.execute(text("UPDATE users SET is_verified = 1 WHERE is_verified IS NULL"))
        conn.execute(text("UPDATE users SET is_verified = 1 WHERE role = 'teacher'"))


def _migrate_chapter_content_column():
    """MySQL TEXT is only 64KB — textbooks need MEDIUMTEXT."""
    if not IS_MYSQL:
        return
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "chapters" not in insp.get_table_names():
        return
    for col in insp.get_columns("chapters"):
        if col["name"] != "content_text":
            continue
        col_type = str(col["type"]).upper()
        if "MEDIUMTEXT" in col_type or "LONGTEXT" in col_type:
            return
        break
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE chapters MODIFY content_text MEDIUMTEXT NULL")
        )


def _migrate_assessment_columns():
    """Add class_level, exam flags for teacher workflow."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tables = set(insp.get_table_names())

    with engine.begin() as conn:
        if "books" in tables:
            cols = {c["name"] for c in insp.get_columns("books")}
            if "class_level" not in cols:
                conn.execute(text("ALTER TABLE books ADD COLUMN class_level INTEGER NULL"))
            rows = conn.execute(text("SELECT id, name FROM books")).fetchall()
            for row in rows:
                name = (row[1] or "").strip()
                level = None
                if name.endswith(" 11") or name.endswith("-11") or " 11 " in name:
                    level = 11
                elif name.endswith(" 12") or name.endswith("-12") or " 12 " in name:
                    level = 12
                if level is not None:
                    conn.execute(
                        text("UPDATE books SET class_level = :lvl WHERE id = :id"),
                        {"lvl": level, "id": row[0]},
                    )

        if "school_classes" in tables:
            cols = {c["name"] for c in insp.get_columns("school_classes")}
            if "grade_level" not in cols:
                conn.execute(
                    text("ALTER TABLE school_classes ADD COLUMN grade_level INTEGER NULL")
                )
            rows = conn.execute(text("SELECT id, name FROM school_classes")).fetchall()
            for row in rows:
                name = (row[1] or "").lower()
                lvl = None
                if "11" in name or "1st" in name or "first" in name or "part 1" in name:
                    lvl = 11
                elif "12" in name or "2nd" in name or "second" in name or "part 2" in name:
                    lvl = 12
                if lvl is not None:
                    conn.execute(
                        text(
                            "UPDATE school_classes SET grade_level = :lvl, name = :n WHERE id = :id"
                        ),
                        {
                            "lvl": lvl,
                            "id": row[0],
                            "n": "11th" if lvl == 11 else "12th",
                        },
                    )

        if "exam_types" in tables:
            cols = {c["name"] for c in insp.get_columns("exam_types")}
            if "is_enabled" not in cols:
                if IS_MYSQL:
                    conn.execute(
                        text("ALTER TABLE exam_types ADD COLUMN is_enabled TINYINT(1) DEFAULT 1")
                    )
                else:
                    conn.execute(
                        text("ALTER TABLE exam_types ADD COLUMN is_enabled INTEGER DEFAULT 1")
                    )
            if "sort_order" not in cols:
                conn.execute(text("ALTER TABLE exam_types ADD COLUMN sort_order INTEGER DEFAULT 0"))

        if "paper_patterns" in tables:
            cols = {c["name"] for c in insp.get_columns("paper_patterns")}
            if "short_attempt" not in cols:
                conn.execute(text("ALTER TABLE paper_patterns ADD COLUMN short_attempt INTEGER NULL"))
            if "long_attempt" not in cols:
                conn.execute(text("ALTER TABLE paper_patterns ADD COLUMN long_attempt INTEGER NULL"))


def init_db():
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_user_columns()
    _migrate_user_roles()
    _migrate_chapter_content_column()
    _migrate_assessment_columns()


def database_info():
    if IS_MYSQL:
        return {"driver": "mysql", "url": DATABASE_URL.split("@")[-1]}
    return {"driver": "sqlite", "path": DB_PATH}
