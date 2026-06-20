import json
import random
import re
import time

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from .db import SessionLocal
from .models import Book, Chapter, ExamType, PaperPattern, Question, SavedPaper, Subject
from .chapter_splitter import split_text_into_chapters
from .exam_sections import FULL_BOOK_TITLE, section_meta_for_exam
from .subject_patterns import apply_subject_pattern, bulk_gen_counts_for_subject
from .question_gen import generate_questions_from_content, trigger_n8n_webhook
from .serializers import question_dict


def save_questions_to_db(db, chapter_id, items, source="gemini"):
    saved = []
    try:
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
    except Exception:
        db.rollback()
        raise


def generate_for_chapter(db, chapter_id, mcq=3, short=2, long=1, use_n8n=False):
    chapter = (
        db.query(Chapter)
        .options(joinedload(Chapter.book).joinedload(Book.subject))
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

    content = (chapter.content_text or "").strip()
    if len(content) < 80:
        raise ValueError(f"Chapter '{chapter.title}' has no text — run Fix Chapters in Admin first.")

    items, _source = generate_questions_from_content(
        chapter.title,
        content,
        mcq_count=mcq,
        short_count=short,
        long_count=long,
        subject_name=(chapter.book.subject.name if chapter.book and chapter.book.subject else ""),
    )
    if not items:
        raise ValueError("AI returned no questions for this chapter.")
    clear_chapter_questions(db, chapter_id)
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


def _pattern_counts(pattern):
    if hasattr(pattern, "mcq_count"):
        return {
            "mcq": int(pattern.mcq_count),
            "short": int(pattern.short_count),
            "long": int(pattern.long_count),
            "marks": int(pattern.total_marks or 0),
            "duration": pattern.duration or "",
            "short_attempt": pattern.short_attempt,
            "long_attempt": pattern.long_attempt,
        }
    return {
        "mcq": int(pattern.get("mcq", 0)),
        "short": int(pattern.get("short", 0)),
        "long": int(pattern.get("long", 0)),
        "marks": int(pattern.get("marks", 0)),
        "duration": pattern.get("duration") or "",
        "short_attempt": pattern.get("short_attempt"),
        "long_attempt": pattern.get("long_attempt"),
    }


def resolve_exam_counts(db, board_id, exam_type_id, subject_name, custom=None):
    """DB pattern + Punjab subject rules (science 17 MCQ, computer 15 MCQ, etc.)."""
    pattern = (
        db.query(PaperPattern)
        .filter(
            PaperPattern.board_id == board_id,
            PaperPattern.exam_type_id == exam_type_id,
        )
        .first()
    )
    exam = db.query(ExamType).filter(ExamType.id == exam_type_id).first()
    exam_code = exam.code if exam else ""

    if custom and exam_code == "class_assessment":
        counts = {
            "mcq": int(custom.get("mcq") or 0),
            "short": int(custom.get("short") or 0),
            "long": int(custom.get("long") or 0),
            "marks": int(custom.get("marks") or 30),
            "duration": custom.get("duration") or "45 minutes",
        }
    elif custom and exam_code != "pre_board":
        base = _pattern_counts(pattern) if pattern else {}
        counts = {
            "mcq": int(custom.get("mcq") if custom.get("mcq") is not None else base.get("mcq", 0)),
            "short": int(
                custom.get("short") if custom.get("short") is not None else base.get("short", 0)
            ),
            "long": int(custom.get("long") if custom.get("long") is not None else base.get("long", 0)),
            "marks": int(custom.get("marks") or base.get("marks") or 30),
            "duration": custom.get("duration") or base.get("duration") or "45 minutes",
        }
    elif pattern:
        counts = _pattern_counts(pattern)
    else:
        raise ValueError("Paper pattern not found for this board and exam type.")

    if exam_code == "pre_board" and subject_name:
        counts = apply_subject_pattern(exam_code, subject_name, counts)

    return counts, pattern, exam_code


def _is_placeholder_question(q):
    if q.source == "seed":
        return True
    text = (q.question_text or "").strip()
    low = text.lower()
    if "concept from" in low or "explain a topic from" in low:
        return True
    if re.match(r"^mcq\s*\d+\s*:", low, re.I):
        return True
    if re.match(r"^short\s*q\s*\d+", low, re.I):
        return True
    if re.match(r"^long\s*q\s*\d+", low, re.I) and "discuss" in low:
        return True
    return False


def _quality_pool(query):
    return [q for q in query.all() if not _is_placeholder_question(q)]


def clear_chapter_questions(db, chapter_id):
    db.query(Question).filter(Question.chapter_id == chapter_id).delete(
        synchronize_session=False
    )
    db.commit()


def question_counts_for_chapters(db, chapter_ids):
    if not chapter_ids:
        return {}
    rows = (
        db.query(Question.chapter_id, func.count(Question.id))
        .filter(Question.chapter_id.in_(chapter_ids))
        .group_by(Question.chapter_id)
        .all()
    )
    return {cid: cnt for cid, cnt in rows}


def pick_questions(db, chapter_ids, pattern, difficulty="mixed", section_flags=None, variety_seed=None):
    counts = _pattern_counts(pattern)
    flags = section_flags or {}
    rng = random.Random(variety_seed if variety_seed is not None else time.time_ns())
    if flags.get("objective") is False:
        counts["mcq"] = 0
    if flags.get("short") is False:
        counts["short"] = 0
    if flags.get("long") is False:
        counts["long"] = 0

    need = {"mcq": counts["mcq"], "short": counts["short"], "long": counts["long"]}
    picked = {"mcq": [], "short": [], "long": []}

    for qtype in picked:
        if need[qtype] < 1:
            continue
        query = db.query(Question).filter(
            Question.chapter_id.in_(chapter_ids),
            Question.question_type == qtype,
        )
        if difficulty and difficulty.lower() != "mixed":
            query = query.filter(Question.difficulty == difficulty.lower())
        pool = _quality_pool(query)
        if len(pool) < need[qtype]:
            label = {"mcq": "MCQ", "short": "short", "long": "long"}.get(qtype, qtype)
            raise ValueError(
                f"Not enough real {label} questions (need {need[qtype]}, have {len(pool)}). "
                "Admin → Books → Fix Chapters → Re-build Questions. "
                "Select more chapters that show question counts."
            )
        rng.shuffle(pool)
        picked[qtype] = pool[: need[qtype]]

    section_titles = {
        "mcq": flags.get("objectiveTitle") or "OBJECTIVE",
        "short": flags.get("shortTitle") or "SUBJECTIVE (SHORT QUESTIONS)",
        "long": flags.get("longTitle") or "SUBJECTIVE (LONG QUESTIONS)",
    }
    sections = []
    if picked["mcq"]:
        sections.append(
            {
                "title": section_titles["mcq"],
                "questionType": "mcq",
                "questions": [question_dict(q) for q in picked["mcq"]],
            }
        )
    if picked["short"]:
        sections.append(
            {
                "title": section_titles["short"],
                "questionType": "short",
                "questions": [question_dict(q) for q in picked["short"]],
            }
        )
    if picked["long"]:
        sections.append(
            {
                "title": section_titles["long"],
                "questionType": "long",
                "questions": [question_dict(q) for q in picked["long"]],
            }
        )
    return sections


def _merge_chapter_text(db, book_id, chapters, book_label="Book"):
    from .content_clean import sanitize_book_text, require_usable_text

    parts = []
    for ch in chapters:
        text = sanitize_book_text(ch.content_text or "")
        if len(text) > 50:
            parts.append(f"--- {ch.title} ---\n{text}")
    if parts:
        return require_usable_text("\n\n".join(parts), book_label)
    fb = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.title == FULL_BOOK_TITLE)
        .first()
    )
    if fb and (fb.content_text or "").strip():
        return require_usable_text(fb.content_text, book_label)
    return ""


def _sections_from_ai_content(content_text, counts, section_flags, label="", subject_name=""):
    """Generate paper sections directly from syllabus text (student-style, no question bank)."""
    mcq_n = int(counts.get("mcq") or 0)
    short_n = int(counts.get("short") or 0)
    long_n = int(counts.get("long") or 0)
    if mcq_n + short_n + long_n < 1:
        raise ValueError("Paper pattern must include at least one question.")

    from .question_gen import generate_questions_batched

    items, gen_info = generate_questions_batched(
        label or "Syllabus",
        content_text,
        mcq_count=mcq_n,
        short_count=short_n,
        long_count=long_n,
        subject_name=subject_name,
    )
    if not items:
        raise ValueError("AI could not create questions. Check GEMINI_API_KEY and try again.")
    demo_mode = bool((gen_info or {}).get("demoFallback"))

    by_type = {"mcq": [], "short": [], "long": []}
    for item in items:
        qt = item.get("questionType")
        if qt in by_type:
            by_type[qt].append(
                {
                    "questionType": qt,
                    "questionText": item.get("questionText") or "",
                    "options": item.get("options") or [],
                    "correctAnswer": item.get("correctAnswer") or "",
                    "difficulty": item.get("difficulty") or "medium",
                }
            )

    flags = section_flags or {}
    section_titles = {
        "mcq": flags.get("objectiveTitle") or "OBJECTIVE",
        "short": flags.get("shortTitle") or "SUBJECTIVE (SHORT QUESTIONS)",
        "long": flags.get("longTitle") or "SUBJECTIVE (LONG QUESTIONS)",
    }
    sections = []
    if mcq_n and by_type["mcq"]:
        sections.append(
            {
                "title": section_titles["mcq"],
                "questionType": "mcq",
                "questions": by_type["mcq"][:mcq_n],
            }
        )
    if short_n and by_type["short"]:
        sections.append(
            {
                "title": section_titles["short"],
                "questionType": "short",
                "questions": by_type["short"][:short_n],
            }
        )
    if long_n and by_type["long"]:
        sections.append(
            {
                "title": section_titles["long"],
                "questionType": "long",
                "questions": by_type["long"][:long_n],
            }
        )
    if not sections:
        raise ValueError("AI returned too few questions. Try again or select more chapters.")
    return sections, demo_mode


def split_book_into_chapters(db, book_id, full_text):
    """Parse full book text into chapter rows (keeps Full Book as backup)."""
    from .models import Book

    book = (
        db.query(Book)
        .options(joinedload(Book.subject))
        .filter(Book.id == book_id)
        .first()
    )
    if not book:
        raise ValueError("Book not found.")
    parts = split_text_into_chapters(
        full_text,
        book_name=book.name if book else None,
        class_level=book.class_level if book else None,
    )
    if not parts:
        return {"created": 0, "message": "Could not detect chapter headings — using Full Book only."}

    existing = {
        c.title: c
        for c in db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.title != FULL_BOOK_TITLE)
        .all()
    }

    created = []
    updated = 0
    seen_titles = set()
    from .content_clean import sanitize_book_text

    for part in parts:
        title = part["title"]
        seen_titles.add(title)
        part_text = sanitize_book_text(part.get("content") or "") or (part.get("content") or "")
        if title in existing:
            row = existing[title]
            row.content_text = part_text
            row.sort_order = part["sortOrder"]
            updated += 1
        else:
            row = Chapter(
                book_id=book_id,
                title=title,
                content_text=part_text,
                sort_order=part["sortOrder"],
            )
            db.add(row)
            created.append(row)

    for title, row in existing.items():
        if title not in seen_titles:
            db.delete(row)

    db.commit()
    all_titles = sorted(seen_titles, key=lambda t: t.lower())
    return {
        "created": len(created),
        "updated": updated,
        "total": len(all_titles),
        "titles": all_titles,
        "message": f"Split into {len(all_titles)} chapters ({len(created)} new, {updated} updated).",
    }


def find_book_pdf_path(book_id):
    from pathlib import Path

    uploads_dir = Path(__file__).resolve().parents[2] / "uploads" / "books"
    if not uploads_dir.is_dir():
        return None
    files = sorted(
        uploads_dir.glob(f"book{book_id}_*.pdf"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def delete_book_pdf_files(book_id):
    """Remove saved PDFs for a book (admin Clear)."""
    from pathlib import Path

    uploads_dir = Path(__file__).resolve().parents[2] / "uploads" / "books"
    if not uploads_dir.is_dir():
        return 0
    removed = 0
    for path in uploads_dir.glob(f"book{book_id}_*.pdf"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def book_is_ready_for_teacher(db, book_id):
    """True when admin uploaded usable chapter text (not empty seed placeholder)."""
    from .content_clean import book_text_usable

    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.title != FULL_BOOK_TITLE)
        .order_by(Chapter.sort_order)
        .all()
    )
    if chapters:
        good = 0
        for ch in chapters:
            text = (ch.content_text or "").strip()
            if len(text) < 80:
                continue
            ok, _reason = book_text_usable(text, min_words=20)
            if ok:
                good += 1
        return good >= 1

    fb = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.title == FULL_BOOK_TITLE)
        .first()
    )
    if not fb:
        return False
    text = (fb.content_text or "").strip()
    if len(text) < 80:
        return False
    ok, _reason = book_text_usable(text, min_words=40)
    return ok


def save_full_book_text(db, book_id, text, title=FULL_BOOK_TITLE):
    from .content_clean import book_text_usable, sanitize_book_text

    raw = (text or "").strip()
    if title == FULL_BOOK_TITLE and len(raw) >= 80:
        ok, result = book_text_usable(raw, min_words=40)
        if not ok:
            from .content_clean import require_usable_text

            book = db.query(Book).filter(Book.id == book_id).first()
            label = book.name if book else "Book"
            require_usable_text(raw, label)
        text = result
    else:
        cleaned = sanitize_book_text(raw)
        if cleaned:
            text = cleaned
        else:
            text = raw
    existing = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.title == title)
        .first()
    )
    if existing:
        existing.content_text = text
        row = existing
    else:
        row = Chapter(book_id=book_id, title=title, content_text=text, sort_order=0)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def process_book_pdf(db, book_id, use_ocr=True):
    """Read saved PDF from disk, extract text (OCR if needed), split chapters."""
    from modules.summarizer.file_reader import read_pdf_from_path

    path = find_book_pdf_path(book_id)
    if not path:
        raise ValueError("No PDF on server for this book. Upload the PDF file first.")

    meta = read_pdf_from_path(
        path, max_pages=500, max_chars=2_000_000, ocr_fallback=use_ocr
    )
    text = (meta.get("text") or "").strip()
    if len(text) < 30:
        raise ValueError(
            "PDF text extract failed. Set GEMINI_API_KEY in backend/.env for scanned books."
        )

    save_full_book_text(db, book_id, text)
    split_info = split_book_into_chapters(db, book_id, text)
    return {
        "pdfFile": path.name,
        "charCount": len(text),
        "ocrUsed": bool(meta.get("ocrUsed")),
        "pageCount": meta.get("pageCount"),
        "split": split_info,
    }


def resplit_book_chapters(db, book_id):
    fb = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.title == FULL_BOOK_TITLE)
        .first()
    )
    if not fb or not (fb.content_text or "").strip():
        raise ValueError("No book text saved. Upload PDF first.")
    return split_book_into_chapters(db, book_id, fb.content_text)


def bulk_generate_for_book(
    db, book_id, mcq_per=None, short_per=None, long_per=None, force=False, only_missing=True
):
    """Generate AI questions for every chapter of a book (excludes Full Book)."""
    book = db.query(Book).options(joinedload(Book.subject)).filter(Book.id == book_id).first()
    if book and book.subject:
        defaults = bulk_gen_counts_for_subject(book.subject.name)
        mcq_per = mcq_per if mcq_per is not None else defaults["mcq"]
        short_per = short_per if short_per is not None else defaults["short"]
        long_per = long_per if long_per is not None else defaults["long"]
    else:
        mcq_per = mcq_per or 6
        short_per = short_per or 4
        long_per = long_per or 2

    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.title != FULL_BOOK_TITLE)
        .order_by(Chapter.sort_order, Chapter.title)
        .all()
    )
    if not chapters:
        fb = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.title == FULL_BOOK_TITLE)
            .first()
        )
        if fb and (fb.content_text or "").strip():
            chapters = [fb]
        else:
            raise ValueError("No chapters found. Upload PDF first.")

    counts_map = question_counts_for_chapters(db, [c.id for c in chapters])
    results = []
    total_q = 0
    for ch in chapters:
        content = (ch.content_text or "").strip()
        if len(content) < 80:
            results.append({"chapter": ch.title, "skipped": "no chapter text — click Fix Chapters"})
            continue
        existing = counts_map.get(ch.id, 0)
        if only_missing and not force and existing >= 5:
            results.append({"chapter": ch.title, "skipped": f"already has {existing} questions"})
            total_q += existing
            continue
        try:
            out = generate_for_chapter(db, ch.id, mcq=mcq_per, short=short_per, long=long_per)
            n = out.get("generated", 0)
            total_q += n
            results.append({"chapter": ch.title, "generated": n})
        except Exception as exc:
            db.rollback()
            results.append({"chapter": ch.title, "error": str(exc)[:200]})

    return {"bookId": book_id, "totalGenerated": total_q, "chapters": results}


def cache_paper_questions(db, chapter_ids, sections):
    """Save generated paper questions so next papers reuse them (no extra API calls)."""
    import json

    from .models import Question

    if not chapter_ids:
        return 0
    added = 0
    idx = 0
    for sec in sections or []:
        for q in sec.get("questions") or []:
            text = (q.get("questionText") or "").strip()
            if len(text) < 8:
                continue
            ch_id = chapter_ids[idx % len(chapter_ids)]
            idx += 1
            db.add(
                Question(
                    chapter_id=ch_id,
                    question_type=q.get("questionType") or sec.get("questionType") or "short",
                    question_text=text,
                    options_json=json.dumps(q.get("options") or []),
                    correct_answer=str(q.get("correctAnswer") or ""),
                    difficulty=q.get("difficulty") or "medium",
                    source="paper_cache",
                )
            )
            added += 1
    if added:
        db.commit()
    return added


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

    custom = filters.get("customPattern") or {}
    counts, pattern, exam_code = resolve_exam_counts(
        db, board_id, exam_type_id, subject.name, custom=custom or None
    )

    if counts["mcq"] + counts["short"] + counts["long"] < 1:
        raise ValueError("Paper pattern must include at least one question.")

    chapter_ids = [c.id for c in chapters]
    section_flags = filters.get("sections") or {}
    variety_seed = filters.get("varietySeed") or time.time_ns()
    use_bank = bool(filters.get("useQuestionBank", False))
    prefer_cache = bool(filters.get("preferCachedQuestions", True))
    source_mode = "ai_direct"
    sections = None

    if prefer_cache or use_bank:
        try:
            sections = pick_questions(
                db,
                chapter_ids,
                counts,
                difficulty,
                section_flags,
                variety_seed=variety_seed,
            )
            source_mode = "question_bank"
        except ValueError:
            sections = None

    if not sections:
        merged = _merge_chapter_text(db, book.id, chapters, book_label=book.name)
        if len(merged) < 80:
            raise ValueError(
                f"{book.name}: book text missing. Admin → Books → upload PDF, "
                "then Fix Chapters."
            )
        sections, demo_mode = _sections_from_ai_content(
            merged,
            counts,
            section_flags,
            label=f"{book.name} syllabus",
            subject_name=subject.name,
        )
        source_mode = "demo_fallback" if demo_mode else "ai_direct"
        if source_mode == "ai_direct" and filters.get("cacheAfterGenerate", True):
            try:
                cache_paper_questions(db, chapter_ids, sections)
            except Exception:
                db.rollback()

    if not sections:
        raise ValueError("Enable at least one paper section (Objective / Short / Long).")

    class_name = filters.get("className") or ""
    exam_name = filters.get("examName") or ""
    title_parts = [subject.name, book.name]
    if class_name:
        title_parts.insert(0, class_name)
    if exam_name:
        title_parts.append(exam_name)

    section_meta = section_meta_for_exam(exam_code, pattern, subject.name)

    return {
        "title": " — ".join(title_parts),
        "marks": counts["marks"],
        "duration": counts["duration"],
        "examCode": exam_code,
        "subjectGroup": counts.get("subject_group"),
        "sectionMeta": section_meta,
        "pattern": {
            "mcqCount": counts["mcq"],
            "shortCount": counts["short"],
            "longCount": counts["long"],
            "shortAttempt": counts.get("short_attempt")
            or (getattr(pattern, "short_attempt", None) if pattern else None),
            "longAttempt": counts.get("long_attempt")
            or (getattr(pattern, "long_attempt", None) if pattern else None),
            "shortBlocks": counts.get("short_blocks"),
        },
        "sections": sections,
        "generatedFrom": source_mode,
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

    from .question_gen import generate_questions_batched

    items, source_info = generate_questions_batched(
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

    demo_mode = bool(source_info.get("demoFallback"))
    meta = meta or {}
    duration = meta.get("duration") or f"{max(30, (mcq + short + long) * 3)} minutes"
    word_count = len((content_text or "").split())
    coverage_note = source_info.get("coverageNote")
    if demo_mode and not coverage_note:
        coverage_note = (
            "Demo mode: paper built from your notes (Gemini API busy/offline). "
            "When the API is available again, regenerate for higher-quality AI questions."
        )
    return {
        "title": meta.get("examTitle") or title,
        "marks": mcq + short * 2 + long * 5,
        "duration": duration,
        "meta": meta,
        "sections": sections,
        "generatedFrom": "demo_fallback" if demo_mode else "ai_direct",
        "sourceInfo": {
            "wordCount": word_count,
            "totalCharacters": source_info.get("totalCharacters", 0),
            "usedCharacters": source_info.get("usedCharacters", 0),
            "fullFileRead": not source_info.get("truncated"),
            "contentLanguage": source_info.get("contentLanguage", "english"),
            "pageCount": source_info.get("pageCount"),
            "coveragePercent": source_info.get("coveragePercent"),
            "sampleWindows": source_info.get("sampleWindows"),
            "coverageNote": coverage_note,
            "demoFallback": demo_mode,
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
