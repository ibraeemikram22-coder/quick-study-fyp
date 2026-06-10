import json
import random

from sqlalchemy.orm import joinedload

from .db import SessionLocal
from .models import Book, Chapter, PaperPattern, Question, SavedPaper, Subject
from .question_gen import generate_questions_from_content, trigger_n8n_webhook
from .serializers import question_dict


def save_questions_to_db(db, chapter_id, items, source="gemini"):
    saved = []
    for item in items:
        row = Question(
            chapter_id=chapter_id,
            question_type=item["questionType"],
            question_text=item["questionText"],
            options_json=json.dumps(item.get("options") or []),
            correct_answer=item.get("correctAnswer") or "",
            difficulty=item.get("difficulty") or "medium",
            source=source,
        )
        db.add(row)
        saved.append(row)
    db.commit()
    for row in saved:
        db.refresh(row)
    return [question_dict(r) for r in saved]


def generate_for_chapter(db, chapter_id, mcq=3, short=2, long=1, use_n8n=False):
    chapter = (
        db.query(Chapter)
        .options(joinedload(Chapter.book))
        .filter(Chapter.id == chapter_id)
        .first()
    )
    if not chapter:
        raise ValueError("Chapter not found.")

    counts = {"mcq": mcq, "short": short, "long": long}

    if use_n8n:
        return {
            "mode": "n8n",
            "chapterId": chapter_id,
            "webhook": trigger_n8n_webhook(
                chapter.id, chapter.title, chapter.content_text or "", counts
            ),
        }

    items, _source = generate_questions_from_content(
        chapter.title,
        chapter.content_text or "",
        mcq_count=mcq,
        short_count=short,
        long_count=long,
    )
    questions = save_questions_to_db(db, chapter_id, items, source="gemini")
    return {
        "mode": "gemini",
        "chapterId": chapter_id,
        "generated": len(questions),
        "questions": questions,
    }


def import_n8n_questions(db, chapter_id, questions_payload):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise ValueError("Chapter not found.")

    items = []
    for raw in questions_payload or []:
        qtype = (raw.get("questionType") or raw.get("type") or "").lower()
        text = (raw.get("questionText") or raw.get("question") or "").strip()
        if qtype not in ("mcq", "short", "long") or not text:
            continue
        items.append(
            {
                "questionType": qtype,
                "questionText": text,
                "options": raw.get("options") or [],
                "correctAnswer": raw.get("correctAnswer") or "",
                "difficulty": raw.get("difficulty") or "medium",
            }
        )
    if not items:
        raise ValueError("No valid questions in payload.")
    saved = save_questions_to_db(db, chapter_id, items, source="n8n")
    return {"imported": len(saved), "questions": saved}


def pick_questions(db, chapter_ids, pattern, difficulty="mixed"):
    need = {
        "mcq": pattern.mcq_count,
        "short": pattern.short_count,
        "long": pattern.long_count,
    }
    picked = {"mcq": [], "short": [], "long": []}

    for qtype in picked:
        query = db.query(Question).filter(
            Question.chapter_id.in_(chapter_ids),
            Question.question_type == qtype,
        )
        if difficulty and difficulty.lower() != "mixed":
            query = query.filter(Question.difficulty == difficulty.lower())
        pool = query.all()
        if len(pool) < need[qtype]:
            raise ValueError(
                f"Not enough {qtype} questions in database "
                f"(need {need[qtype]}, have {len(pool)}). "
                "Generate more in Admin panel."
            )
        picked[qtype] = random.sample(pool, need[qtype])

    sections = []
    sections.append(
        {
            "title": "Section A — MCQs",
            "questions": [question_dict(q) for q in picked["mcq"]],
        }
    )
    sections.append(
        {
            "title": "Section B — Short Questions",
            "questions": [question_dict(q) for q in picked["short"]],
        }
    )
    sections.append(
        {
            "title": "Section C — Long Questions",
            "questions": [question_dict(q) for q in picked["long"]],
        }
    )
    return sections


def generate_paper(db, filters):
    subject_name = filters.get("subject")
    book_name = filters.get("book")
    chapter_titles = filters.get("chapters") or []
    board_id = filters.get("boardId")
    exam_type_id = filters.get("examTypeId")
    difficulty = filters.get("difficulty") or "mixed"

    subject = db.query(Subject).filter(Subject.name == subject_name).first()
    if not subject:
        raise ValueError(f"Subject '{subject_name}' not found.")

    book = (
        db.query(Book)
        .filter(Book.subject_id == subject.id, Book.name == book_name)
        .first()
    )
    if not book:
        raise ValueError(f"Book '{book_name}' not found.")

    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book.id, Chapter.title.in_(chapter_titles))
        .all()
    )
    if not chapters:
        raise ValueError("No matching chapters selected.")

    pattern = (
        db.query(PaperPattern)
        .filter(
            PaperPattern.board_id == board_id,
            PaperPattern.exam_type_id == exam_type_id,
        )
        .first()
    )
    if not pattern:
        raise ValueError("Paper pattern not found for this board and exam type.")

    chapter_ids = [c.id for c in chapters]
    sections = pick_questions(db, chapter_ids, pattern, difficulty)

    return {
        "title": f"{subject.name} — {book.name} Paper",
        "marks": pattern.total_marks,
        "duration": pattern.duration,
        "pattern": {
            "mcqCount": pattern.mcq_count,
            "shortCount": pattern.short_count,
            "longCount": pattern.long_count,
        },
        "sections": sections,
    }


def generate_paper_from_notes(
    content_text, counts, title="Student Practice Paper", meta=None, page_count=None
):
    """AI paper from pasted notes or uploaded file (no question bank)."""
    mcq = int(counts.get("mcq") or 0)
    short = int(counts.get("short") or 0)
    long = int(counts.get("long") or 0)
    if mcq + short + long < 1:
        raise ValueError("Select at least one question type with count > 0.")

    items, source_info = generate_questions_from_content(
        "Uploaded notes",
        content_text,
        mcq_count=mcq,
        short_count=short,
        long_count=long,
        page_count=page_count,
    )

    by_type = {"mcq": [], "short": [], "long": []}
    for item in items:
        qtype = item["questionType"]
        if qtype in by_type and len(by_type[qtype]) < counts.get(qtype, 0):
            by_type[qtype].append(
                {
                    "questionType": qtype,
                    "questionText": item["questionText"],
                    "options": item.get("options") or [],
                    "correctAnswer": item.get("correctAnswer") or "",
                    "difficulty": item.get("difficulty") or "medium",
                }
            )

    sections = []
    if by_type["mcq"]:
        sections.append(
            {
                "title": "Section A — MCQs",
                "questions": by_type["mcq"],
            }
        )
    if by_type["short"]:
        sections.append(
            {
                "title": "Section B — Short Questions",
                "questions": by_type["short"],
            }
        )
    if by_type["long"]:
        sections.append(
            {
                "title": "Section C — Long Questions",
                "questions": by_type["long"],
            }
        )

    total = sum(len(s["questions"]) for s in sections)
    if total < 1:
        raise ValueError("AI did not return usable questions. Try again.")

    meta = meta or {}
    duration = meta.get("duration") or f"{max(30, (mcq + short + long) * 3)} minutes"
    word_count = len((content_text or "").split())
    return {
        "title": meta.get("examTitle") or title,
        "marks": mcq + short * 2 + long * 5,
        "duration": duration,
        "meta": meta,
        "sections": sections,
        "sourceInfo": {
            "wordCount": word_count,
            "totalCharacters": source_info.get("totalCharacters", 0),
            "usedCharacters": source_info.get("usedCharacters", 0),
            "fullFileRead": not source_info.get("truncated"),
            "contentLanguage": source_info.get("contentLanguage", "english"),
            "pageCount": source_info.get("pageCount"),
            "coveragePercent": source_info.get("coveragePercent"),
            "sampleWindows": source_info.get("sampleWindows"),
            "coverageNote": source_info.get("coverageNote"),
        },
    }


def save_paper(db, title, paper_payload, filters, user_id=None, module="questionbank", mode=""):
    row = SavedPaper(
        title=title or "Generated Paper",
        payload_json=json.dumps(paper_payload),
        filters_json=json.dumps(filters),
        user_id=user_id,
        module=module,
        mode=mode or (filters or {}).get("mode") or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id
