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


def init_db():
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def database_info():
    if IS_MYSQL:
        return {"driver": "mysql", "url": DATABASE_URL.split("@")[-1]}
    return {"driver": "sqlite", "path": DB_PATH}
