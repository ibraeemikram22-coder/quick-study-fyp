from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import relationship

from .db import Base


class Board(Base):
    __tablename__ = "boards"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    code = Column(String(40), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    classes = relationship("SchoolClass", back_populates="board")
    patterns = relationship("PaperPattern", back_populates="board")


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    grade_level = Column(Integer, nullable=True)  # 11 or 12
    board_id = Column(Integer, ForeignKey("boards.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    board = relationship("Board", back_populates="classes")


class ExamType(Base):
    __tablename__ = "exam_types"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    code = Column(String(40), unique=True, nullable=False)
    is_enabled = Column(Integer, default=1)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    patterns = relationship("PaperPattern", back_populates="exam_type")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    books = relationship("Book", back_populates="subject", cascade="all, delete-orphan")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String(160), nullable=False)
    class_level = Column(Integer, nullable=True)  # 11 or 12 — ties book to class
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("subject_id", "name", name="uq_book_subject_name"),)

    subject = relationship("Subject", back_populates="books")
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content_text = Column(Text().with_variant(MEDIUMTEXT(), "mysql"), default="")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("book_id", "title", name="uq_chapter_book_title"),)

    book = relationship("Book", back_populates="chapters")
    questions = relationship("Question", back_populates="chapter", cascade="all, delete-orphan")


class PaperPattern(Base):
    __tablename__ = "paper_patterns"

    id = Column(Integer, primary_key=True)
    board_id = Column(Integer, ForeignKey("boards.id"), nullable=False)
    exam_type_id = Column(Integer, ForeignKey("exam_types.id"), nullable=False)
    mcq_count = Column(Integer, default=15)
    short_count = Column(Integer, default=10)
    long_count = Column(Integer, default=5)
    short_attempt = Column(Integer, nullable=True)
    long_attempt = Column(Integer, nullable=True)
    total_marks = Column(Integer, default=100)
    duration = Column(String(40), default="3 Hours")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("board_id", "exam_type_id", name="uq_pattern_board_exam"),
    )

    board = relationship("Board", back_populates="patterns")
    exam_type = relationship("ExamType", back_populates="patterns")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    question_type = Column(String(20), nullable=False)  # mcq | short | long
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, default="[]")
    correct_answer = Column(Text, default="")
    difficulty = Column(String(20), default="medium")
    source = Column(String(30), default="manual")  # manual | gemini | n8n
    created_at = Column(DateTime, default=datetime.utcnow)

    chapter = relationship("Chapter", back_populates="questions")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="student")  # student | teacher | admin
    is_verified = Column(Integer, default=1)  # 0 = pending (teachers), 1 = verified
    verify_code = Column(String(10), nullable=True)
    verify_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SavedPaper(Base):
    __tablename__ = "saved_papers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    module = Column(String(40), default="questionbank")
    mode = Column(String(30), default="")
    title = Column(String(200), default="Generated Paper")
    payload_json = Column(Text, nullable=False)
    filters_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class ContactFeedback(Base):
    __tablename__ = "contact_feedback"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), default="Anonymous")
    email = Column(String(180), default="")
    subject = Column(String(200), default="feedback")
    message = Column(Text, nullable=False)
    rating = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    module = Column(String(40), nullable=False)
    action = Column(String(80), nullable=False)
    details_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class ModuleRecord(Base):
    __tablename__ = "module_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    module = Column(String(40), nullable=False)
    title = Column(String(300), default="")
    input_preview = Column(Text, default="")
    result_json = Column(Text, nullable=False)
    meta_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class TranscriptRecord(Base):
    __tablename__ = "transcript_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    input_type = Column(String(20), default="youtube")  # youtube | upload
    source_label = Column(String(500), default="")
    source_engine = Column(String(40), default="")
    word_count = Column(Integer, default=0)
    transcript_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
