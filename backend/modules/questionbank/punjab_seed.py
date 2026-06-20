"""
Punjab Board default setup — safe to run many times (upsert).
Run: cd backend && python -m modules.questionbank.punjab_seed
"""
import json

from .db import SessionLocal, init_db
from .models import (
    Board,
    Book,
    Chapter,
    ExamType,
    PaperPattern,
    Question,
    SchoolClass,
    Subject,
)

SUBJECTS = ["Physics", "Chemistry", "Biology", "Computer"]

BOOKS_BY_SUBJECT = {
    "Physics": ["Physics 11", "Physics 12"],
    "Chemistry": ["Chemistry 11", "Chemistry 12"],
    "Biology": ["Biology 11", "Biology 12"],
    "Computer": ["Computer 11", "Computer 12"],
}

# mcq, short_printed, long_printed, marks, duration, sort, short_attempt, long_attempt
# Punjab Board style: pre-board has MCQs compulsory; short/long have choice (attempt X of Y)
EXAM_PATTERNS = [
    ("weekly", "Weekly Test", 6, 12, 1, 30, "45 minutes", 1, 12, 1),
    ("monthly", "Monthly Test", 6, 12, 1, 30, "45 minutes", 2, 12, 1),
    ("quarter", "Quarterly Test", 6, 12, 1, 30, "45 minutes", 3, 12, 1),
    ("half_book", "Half Book Exam", 12, 10, 4, 65, "2.5 Hours", 4, 6, 2),
    ("pre_board", "Pre-Board Exam", 17, 12, 5, 85, "3 Hours", 5, 8, 3),
    ("class_assessment", "Class Assessment", 6, 12, 1, 30, "45 minutes", 6, 12, 1),
]

CLASS_ROWS = [
    ("11th", 11),
    ("12th", 12),
]

LEGACY_BOOK_NAMES = {
    "PTB Physics",
    "Federal Physics",
    "Physics 11 — Punjab",
}
LEGACY_BOARD_CODES = {"fbise", "federal", "punjab_mukabbir"}
LEGACY_EXAM_CODES = {"mid", "pre"}  # old seed; replaced by weekly / pre_board

def cleanup_english_and_seed(db):
    """Remove English books and all placeholder seed questions."""
    removed = {"englishBooks": 0, "seedQuestions": 0, "demoChapters": 0}

    seed_q = db.query(Question).filter(Question.source == "seed").all()
    for q in seed_q:
        db.delete(q)
    removed["seedQuestions"] = len(seed_q)

    eng = db.query(Subject).filter(Subject.name == "English").first()
    if eng:
        books = db.query(Book).filter(Book.subject_id == eng.id).all()
        removed["englishBooks"] = len(books)
        for book in books:
            db.delete(book)
        db.delete(eng)

    for title in ("Ch 1 — Measurement", "Ch 2 — Vectors & Equilibrium", "Ch 3 — Motion & Force"):
        for ch in db.query(Chapter).filter(Chapter.title == title).all():
            db.delete(ch)
            removed["demoChapters"] += 1

    db.flush()
    return removed


def _get_or_create_board(db, name, code):
    row = db.query(Board).filter(Board.code == code).first()
    if row:
        row.name = name
        return row
    legacy = db.query(Board).filter(Board.code == "punjab_mukabbir").first()
    if legacy:
        legacy.name = name
        legacy.code = code
        return legacy
    row = Board(name=name, code=code)
    db.add(row)
    db.flush()
    return row


def _get_or_create_exam(db, name, code, sort_order=0):
    row = db.query(ExamType).filter(ExamType.code == code).first()
    if row:
        row.name = name
        row.sort_order = sort_order
        row.is_enabled = 1
        return row
    row = ExamType(name=name, code=code, sort_order=sort_order, is_enabled=1)
    db.add(row)
    db.flush()
    return row


def _normalize_subjects(db):
    cs = db.query(Subject).filter(Subject.name == "Computer Science").first()
    comp = db.query(Subject).filter(Subject.name == "Computer").first()
    if cs and not comp:
        cs.name = "Computer"
    elif cs and comp:
        for book in db.query(Book).filter(Book.subject_id == cs.id).all():
            book.subject_id = comp.id
        db.delete(cs)


def _get_or_create_subject(db, name):
    row = db.query(Subject).filter(Subject.name == name).first()
    if not row:
        row = Subject(name=name)
        db.add(row)
        db.flush()
    return row


def _book_class_level(name):
    if name.endswith(" 11") or name.endswith("-11"):
        return 11
    if name.endswith(" 12") or name.endswith("-12"):
        return 12
    return None


def _get_or_create_book(db, subject_id, name):
    row = db.query(Book).filter(Book.subject_id == subject_id, Book.name == name).first()
    level = _book_class_level(name)
    if not row:
        row = Book(subject_id=subject_id, name=name, class_level=level)
        db.add(row)
        db.flush()
    else:
        row.class_level = level
    return row


def _get_or_create_pattern(
    db, board_id, exam_id, mcq, short, long, marks, duration, short_attempt=None, long_attempt=None
):
    row = (
        db.query(PaperPattern)
        .filter(PaperPattern.board_id == board_id, PaperPattern.exam_type_id == exam_id)
        .first()
    )
    if row:
        row.mcq_count = mcq
        row.short_count = short
        row.long_count = long
        row.total_marks = marks
        row.duration = duration
        row.short_attempt = short_attempt
        row.long_attempt = long_attempt
        return row
    row = PaperPattern(
        board_id=board_id,
        exam_type_id=exam_id,
        mcq_count=mcq,
        short_count=short,
        long_count=long,
        short_attempt=short_attempt,
        long_attempt=long_attempt,
        total_marks=marks,
        duration=duration,
    )
    db.add(row)
    db.flush()
    return row


def cleanup_legacy_data(db):
    """Remove Federal board, PTB/Federal Physics, old exam types."""
    removed = {"boards": [], "books": [], "exams": []}

    for name in LEGACY_BOOK_NAMES:
        for book in db.query(Book).filter(Book.name == name).all():
            removed["books"].append(book.name)
            db.delete(book)

    for book in db.query(Book).all():
        low = (book.name or "").lower()
        if "federal" in low and book.name not in removed["books"]:
            removed["books"].append(book.name)
            db.delete(book)

    boards = db.query(Board).all()
    for board in boards:
        code = (board.code or "").lower()
        name = (board.name or "").lower()
        if code in LEGACY_BOARD_CODES or code == "fbise" or "federal" in name or name == "fbise":
            if board.code == "punjab":
                continue
            db.query(PaperPattern).filter(PaperPattern.board_id == board.id).delete()
            db.query(SchoolClass).filter(SchoolClass.board_id == board.id).delete()
            removed["boards"].append(board.name)
            db.delete(board)

    has_pre_board = db.query(ExamType).filter(ExamType.code == "pre_board").first()
    for code in LEGACY_EXAM_CODES:
        if code == "pre" and not has_pre_board:
            continue
        exam = db.query(ExamType).filter(ExamType.code == code).first()
        if exam:
            db.query(PaperPattern).filter(PaperPattern.exam_type_id == exam.id).delete()
            removed["exams"].append(f"{exam.name} ({exam.code})")
            db.delete(exam)

    db.flush()
    return removed


def ensure_punjab_data(add_demo_questions=False, add_demo_chapters=False):
    init_db()
    db = SessionLocal()
    try:
        cleanup = cleanup_legacy_data(db)
        cleanup_extra = cleanup_english_and_seed(db)
        cleanup["englishAndSeed"] = cleanup_extra
        _normalize_subjects(db)
        board = _get_or_create_board(db, "Punjab Board", "punjab")

        for cls_name, grade in CLASS_ROWS:
            row = (
                db.query(SchoolClass)
                .filter(SchoolClass.board_id == board.id, SchoolClass.grade_level == grade)
                .first()
            )
            if row:
                row.name = cls_name
                row.grade_level = grade
            else:
                db.add(SchoolClass(name=cls_name, grade_level=grade, board_id=board.id))

        for code, name, mcq, short, long, marks, dur, sort_ord, s_att, l_att in EXAM_PATTERNS:
            ex = _get_or_create_exam(db, name, code, sort_ord)
            _get_or_create_pattern(db, board.id, ex.id, mcq, short, long, marks, dur, s_att, l_att)

        subjects = {}
        books_created = []
        for sname in SUBJECTS:
            subjects[sname] = _get_or_create_subject(db, sname)
            for bname in BOOKS_BY_SUBJECT[sname]:
                book = _get_or_create_book(db, subjects[sname].id, bname)
                books_created.append(f"{sname}: {bname}")

        old_physics = (
            db.query(Book)
            .filter(Book.subject_id == subjects["Physics"].id, Book.name == "Physics 11 — Punjab")
            .first()
        )
        if old_physics:
            target = (
                db.query(Book)
                .filter(Book.subject_id == subjects["Physics"].id, Book.name == "Physics 11")
                .first()
            )
            if target and target.id != old_physics.id:
                for ch in db.query(Chapter).filter(Chapter.book_id == old_physics.id).all():
                    ch.book_id = target.id
                db.delete(old_physics)
            else:
                old_physics.name = "Physics 11"

        db.commit()
        return {
            "board": board.name,
            "subjects": len(SUBJECTS),
            "books": len(books_created),
            "bookList": books_created,
            "examTypes": len(EXAM_PATTERNS),
            "removedLegacy": cleanup,
        }
    finally:
        db.close()


# Backward-compatible alias
ensure_mukabbir_data = ensure_punjab_data


if __name__ == "__main__":
    result = ensure_punjab_data()
    print("Punjab setup OK:", result)
