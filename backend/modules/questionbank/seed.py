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


def run_seed():
    init_db()
    db = SessionLocal()
    try:
        if db.query(Board).count() > 0:
            return False

        punjab = Board(name="Punjab Board", code="punjab")
        fbise = Board(name="FBISE", code="fbise")
        db.add_all([punjab, fbise])
        db.flush()

        db.add_all(
            [
                SchoolClass(name="1st Year", board_id=punjab.id),
                SchoolClass(name="2nd Year", board_id=punjab.id),
            ]
        )

        mid = ExamType(name="Mids", code="mid")
        quarter = ExamType(name="1/4", code="quarter")
        pre = ExamType(name="Pre Board", code="pre")
        db.add_all([mid, quarter, pre])
        db.flush()

        physics = Subject(name="Physics")
        chemistry = Subject(name="Chemistry")
        math = Subject(name="Math")
        english = Subject(name="English")
        urdu = Subject(name="Urdu")
        db.add_all([physics, chemistry, math, english, urdu])
        db.flush()

        ptb_physics = Book(subject_id=physics.id, name="PTB Physics")
        federal_physics = Book(subject_id=physics.id, name="Federal Physics")
        db.add_all([ptb_physics, federal_physics])
        db.flush()

        db.add_all(
            [
                Chapter(
                    book_id=ptb_physics.id,
                    title="Ch1 Motion",
                    content_text="Motion is the change in position of an object over time.",
                    sort_order=1,
                ),
                Chapter(
                    book_id=ptb_physics.id,
                    title="Ch2 Force",
                    content_text="Force causes acceleration. F = ma.",
                    sort_order=2,
                ),
                Chapter(
                    book_id=federal_physics.id,
                    title="Ch1 Vectors",
                    content_text="Vectors have magnitude and direction.",
                    sort_order=1,
                ),
            ]
        )

        db.add_all(
            [
                PaperPattern(
                    board_id=punjab.id,
                    exam_type_id=mid.id,
                    mcq_count=20,
                    short_count=8,
                    long_count=3,
                ),
                PaperPattern(
                    board_id=fbise.id,
                    exam_type_id=mid.id,
                    mcq_count=15,
                    short_count=10,
                    long_count=5,
                ),
            ]
        )
        db.flush()

        ch1, ch2, ch3 = (
            db.query(Chapter)
            .order_by(Chapter.id)
            .limit(3)
            .all()
        )
        sample = []
        for ch in (ch1, ch2, ch3):
            if not ch:
                continue
            for i in range(25):
                sample.append(
                    Question(
                        chapter_id=ch.id,
                        question_type="mcq",
                        question_text=f"MCQ {i+1} from {ch.title}?",
                        options_json=json.dumps(["A", "B", "C", "D"]),
                        correct_answer="A",
                        difficulty="medium",
                        source="seed",
                    )
                )
            for i in range(12):
                sample.append(
                    Question(
                        chapter_id=ch.id,
                        question_type="short",
                        question_text=f"Short Q{i+1}: Explain a concept from {ch.title}.",
                        options_json="[]",
                        correct_answer="Sample answer",
                        difficulty="medium",
                        source="seed",
                    )
                )
            for i in range(8):
                sample.append(
                    Question(
                        chapter_id=ch.id,
                        question_type="long",
                        question_text=f"Long Q{i+1}: Discuss {ch.title} in detail.",
                        options_json="[]",
                        correct_answer="Detailed outline",
                        difficulty="hard",
                        source="seed",
                    )
                )
        db.add_all(sample)

        db.commit()
        return True
    finally:
        db.close()
