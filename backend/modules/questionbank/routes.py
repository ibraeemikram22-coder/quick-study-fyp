import json

from flask import Blueprint, jsonify, request, send_file
from io import BytesIO
from sqlalchemy.orm import joinedload

from .db import SessionLocal, init_db
from .models import (
    Board,
    Book,
    Chapter,
    ExamType,
    PaperPattern,
    Question,
    SavedPaper,
    SchoolClass,
    Subject,
)
from .punjab_seed import ensure_punjab_data
from .seed import run_seed
from .serializers import (
    board_dict,
    book_dict,
    chapter_dict,
    class_dict,
    exam_dict,
    pattern_dict,
    question_dict,
    subject_dict,
)
from .service import (
    bulk_generate_for_book,
    generate_for_chapter,
    generate_paper,
    generate_paper_from_notes,
    import_n8n_questions,
    process_book_pdf,
    question_counts_for_chapters,
    resplit_book_chapters,
    save_full_book_text,
    save_paper,
    split_book_into_chapters,
)

questionbank_bp = Blueprint("questionbank", __name__)


def _ok(data=None, **extra):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload)


def _err(message, code=400):
    return jsonify({"success": False, "error": message}), code


def _db():
    return SessionLocal()


def _json_body():
    return request.get_json(silent=True) or {}


@questionbank_bp.route("/api/questionbank/health", methods=["GET"])
def health():
    init_db()
    return _ok({"status": "questionbank ready"})


_GEMINI_CHECK_CACHE = {"ts": 0, "payload": None}


@questionbank_bp.route("/api/questionbank/gemini-usage", methods=["GET"])
def gemini_usage_route():
    """Daily API usage stats (key never exposed)."""
    from modules.gemini_usage import get_usage

    return _ok(get_usage())


@questionbank_bp.route("/api/questionbank/gemini-check", methods=["GET"])
def gemini_check():
    """Quick Gemini API key / quota check (one tiny request)."""
    import os
    import time

    import requests

    from modules.gemini_config import format_gemini_failure, gemini_model_chain, gemini_url

    force = request.args.get("refresh") == "1"
    now = time.time()
    if (
        not force
        and _GEMINI_CHECK_CACHE["payload"]
        and now - _GEMINI_CHECK_CACHE["ts"] < 600
    ):
        return _ok(_GEMINI_CHECK_CACHE["payload"])

    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    from modules.gemini_usage import get_usage

    usage = get_usage()
    if not api_key:
        payload = {
            "ok": False,
            "reason": "missing_key",
            "message": "AI service is not configured. Please contact your administrator.",
            "usage": usage,
        }
        _GEMINI_CHECK_CACHE.update(ts=now, payload=payload)
        return _ok(payload)

    body = {
        "contents": [{"parts": [{"text": 'Reply JSON: {"ping":1}'}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
    }
    model = gemini_model_chain()[0]
    try:
        res = requests.post(
            gemini_url(model),
            params={"key": api_key},
            json=body,
            timeout=45,
        )
    except Exception as exc:
        payload = {"ok": False, "reason": "network", "message": str(exc)[:200]}
        _GEMINI_CHECK_CACHE.update(ts=now, payload=payload)
        return _ok(payload)

    if res.ok:
        payload = {
            "ok": True,
            "model": model,
            "message": "AI service is available.",
            "usage": usage,
        }
        _GEMINI_CHECK_CACHE.update(ts=now, payload=payload)
        return _ok(payload)

    from modules.questionbank.question_gen import demo_fallback_enabled

    msg = format_gemini_failure(res.status_code, res.text)
    reason = "quota_exceeded" if res.status_code == 429 and "quota" in res.text.lower() else "api_error"
    if reason == "quota_exceeded" and demo_fallback_enabled():
        payload = {
            "ok": True,
            "demoFallback": True,
            "reason": reason,
            "status": res.status_code,
            "message": "Daily AI quota reached. Papers will use saved book content until tomorrow.",
            "usage": usage,
        }
        _GEMINI_CHECK_CACHE.update(ts=now, payload=payload)
        return _ok(payload)
    payload = {
        "ok": False,
        "reason": reason,
        "status": res.status_code,
        "message": msg,
        "usage": usage,
    }
    _GEMINI_CHECK_CACHE.update(ts=now, payload=payload)
    return _ok(payload)


@questionbank_bp.route("/api/questionbank/seed", methods=["POST"])
def seed_data():
    created = run_seed()
    return _ok({"seeded": created, "message": "Sample data added" if created else "Already seeded"})


@questionbank_bp.route("/api/questionbank/setup-punjab", methods=["POST"])
def setup_punjab():
    """Punjab Board, exam patterns, subject books (Physics, Chemistry, Biology, Computer)."""
    summary = ensure_punjab_data()
    return _ok(summary, message="Punjab Board setup complete")


@questionbank_bp.route("/api/questionbank/setup-mukabbir", methods=["POST"])
def setup_mukabbir_legacy():
    """Legacy URL — same as setup-punjab."""
    return setup_punjab()


@questionbank_bp.route("/api/questionbank/metadata", methods=["GET"])
def metadata():
    db = _db()
    try:
        boards = [board_dict(b) for b in db.query(Board).order_by(Board.name).all()]
        classes = [class_dict(c) for c in db.query(SchoolClass).order_by(SchoolClass.name).all()]
        exams = [exam_dict(e) for e in db.query(ExamType).order_by(ExamType.name).all()]
        subjects = [
            subject_dict(s)
            for s in db.query(Subject).filter(Subject.name != "English").order_by(Subject.name).all()
        ]
        patterns = [
            pattern_dict(p)
            for p in db.query(PaperPattern)
            .options(
                joinedload(PaperPattern.board),
                joinedload(PaperPattern.exam_type),
            )
            .all()
        ]
        return _ok(
            {
                "boards": boards,
                "classes": classes,
                "examTypes": exams,
                "subjects": subjects,
                "patterns": patterns,
            }
        )
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/teacher/metadata", methods=["GET"])
def teacher_metadata():
    """Punjab Board teacher dashboard — classes 11/12, enabled exams, patterns."""
    db = _db()
    try:
        board = (
            db.query(Board)
            .filter(Board.code.in_(["punjab", "punjab_mukabbir"]))
            .order_by(Board.id)
            .first()
        )
        if not board:
            board = db.query(Board).order_by(Board.id).first()

        classes = (
            db.query(SchoolClass)
            .filter(SchoolClass.board_id == board.id if board else True)
            .order_by(SchoolClass.grade_level, SchoolClass.name)
            .all()
        )
        if not classes:
            classes = db.query(SchoolClass).order_by(SchoolClass.name).all()

        exams = (
            db.query(ExamType)
            .filter(ExamType.is_enabled != 0)
            .order_by(ExamType.sort_order, ExamType.name)
            .all()
        )
        patterns = []
        if board:
            patterns = [
                pattern_dict(p)
                for p in db.query(PaperPattern)
                .options(
                    joinedload(PaperPattern.board),
                    joinedload(PaperPattern.exam_type),
                )
                .filter(PaperPattern.board_id == board.id)
                .all()
            ]

        from .service import book_is_ready_for_teacher

        all_books = (
            db.query(Book)
            .options(joinedload(Book.subject))
            .join(Subject)
            .filter(Subject.name != "English")
            .order_by(Book.class_level, Book.name)
            .all()
        )
        books = [b for b in all_books if book_is_ready_for_teacher(db, b.id)]

        return _ok(
            {
                "institution": "Mukabbir College Gujrat",
                "board": board_dict(board) if board else None,
                "classes": [class_dict(c) for c in classes],
                "examTypes": [exam_dict(e) for e in exams],
                "patterns": patterns,
                "books": [book_dict(b) for b in books],
                "subjects": [subject_dict(s) for s in db.query(Subject).order_by(Subject.name).all()],
            }
        )
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/books", methods=["GET"])
def list_books():
    db = _db()
    try:
        subject_id = request.args.get("subjectId", type=int)
        subject_name = request.args.get("subject")
        class_level = request.args.get("classLevel", type=int)
        query = db.query(Book).options(joinedload(Book.subject))
        if subject_id:
            query = query.filter(Book.subject_id == subject_id)
        elif subject_name:
            sub = db.query(Subject).filter(Subject.name == subject_name).first()
            if not sub:
                return _ok([])
            query = query.filter(Book.subject_id == sub.id)
        if class_level:
            query = query.filter(Book.class_level == class_level)
        rows = query.order_by(Book.name).all()
        return _ok([book_dict(b) for b in rows])
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/chapters", methods=["GET"])
def list_chapters():
    db = _db()
    try:
        book_id = request.args.get("bookId", type=int)
        book_name = request.args.get("book")
        subject_name = request.args.get("subject")
        query = db.query(Chapter).options(joinedload(Chapter.book), joinedload(Chapter.questions))
        if book_id:
            query = query.filter(Chapter.book_id == book_id)
        elif book_name:
            book_q = db.query(Book).options(joinedload(Book.subject))
            if subject_name:
                sub = db.query(Subject).filter(Subject.name == subject_name).first()
                if not sub:
                    return _ok([])
                book_q = book_q.filter(Book.subject_id == sub.id, Book.name == book_name)
            else:
                book_q = book_q.filter(Book.name == book_name)
            book = book_q.first()
            if not book:
                return _ok([])
            query = query.filter(Chapter.book_id == book.id)
        rows = query.order_by(Chapter.sort_order, Chapter.title).all()
        named = [c for c in rows if c.title != "Full Book"]
        if named:
            rows = named
        from .content_clean import book_text_usable

        qmap = question_counts_for_chapters(db, [c.id for c in rows])
        out = []
        for c in rows:
            row = chapter_dict(c, question_count=qmap.get(c.id, 0))
            ok, reason = book_text_usable(c.content_text or "", min_words=30)
            row["textQuality"] = "ok" if ok else reason
            out.append(row)
        return _ok(out)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/pattern", methods=["GET"])
def get_pattern():
    from .service import resolve_exam_counts

    db = _db()
    try:
        board_id = request.args.get("boardId", type=int)
        exam_id = request.args.get("examTypeId", type=int)
        subject_name = (request.args.get("subject") or "").strip()
        board_code = request.args.get("board")
        exam_code = request.args.get("exam")
        query = db.query(PaperPattern).options(
            joinedload(PaperPattern.board),
            joinedload(PaperPattern.exam_type),
        )
        if board_id and exam_id:
            row = query.filter(
                PaperPattern.board_id == board_id,
                PaperPattern.exam_type_id == exam_id,
            ).first()
        elif board_code and exam_code:
            row = (
                query.join(Board)
                .join(ExamType)
                .filter(Board.code == board_code, ExamType.code == exam_code)
                .first()
            )
        else:
            return _err("boardId+examTypeId or board+exam required")
        if not row:
            return _err("Pattern not found", 404)
        data = pattern_dict(row)
        if subject_name and board_id and exam_id:
            counts, _, _ = resolve_exam_counts(db, board_id, exam_id, subject_name)
            data["mcqCount"] = counts["mcq"]
            data["shortCount"] = counts["short"]
            data["longCount"] = counts["long"]
            data["totalMarks"] = counts["marks"]
            data["duration"] = counts["duration"]
            data["shortAttempt"] = counts.get("short_attempt")
            data["longAttempt"] = counts.get("long_attempt")
            data["shortBlocks"] = counts.get("short_blocks")
            data["subjectGroup"] = counts.get("subject_group")
        return _ok(data)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/questions", methods=["GET"])
def list_questions():
    db = _db()
    try:
        chapter_id = request.args.get("chapterId", type=int)
        qtype = request.args.get("type")
        query = db.query(Question)
        if chapter_id:
            query = query.filter(Question.chapter_id == chapter_id)
        if qtype:
            query = query.filter(Question.question_type == qtype.lower())
        rows = query.order_by(Question.id.desc()).limit(200).all()
        return _ok([question_dict(q) for q in rows])
    finally:
        db.close()


def _export_paper_docx():
    from .paper_export import build_paper_docx

    body = _json_body()
    paper = body.get("paper")
    if not paper or not paper.get("sections"):
        return None, None, _err("paper with sections required")
    meta = body.get("meta") or {}
    include_key = bool(body.get("includeAnswerKey"))
    meta["includeAnswerKey"] = include_key
    if not meta.get("institute"):
        meta["institute"] = "Mukabbir College Gujrat"
    blob = build_paper_docx(paper, meta)
    return blob, meta, None


def _send_paper_docx_response(blob, meta):
    filename = (meta.get("examTitle") or "exam-paper").replace(" ", "-")[:40]
    return send_file(
        BytesIO(blob),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"{filename}.docx",
    )


@questionbank_bp.route("/api/questionbank/student/export-docx", methods=["POST"])
def student_export_docx():
    """Download editable Word paper with aligned header."""
    try:
        blob, meta, err = _export_paper_docx()
        if err:
            return err
        return _send_paper_docx_response(blob, meta)
    except RuntimeError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc), 500)


@questionbank_bp.route("/api/questionbank/papers/export-docx", methods=["POST"])
def teacher_export_docx():
    """Teacher dashboard — download board-style paper as Word (print to PDF in Word)."""
    try:
        blob, meta, err = _export_paper_docx()
        if err:
            return err
        return _send_paper_docx_response(blob, meta)
    except RuntimeError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc), 500)


@questionbank_bp.route("/api/questionbank/student/generate", methods=["POST"])
def student_generate():
    """Generate practice paper from pasted text or uploaded PDF/DOCX/TXT."""
    try:
        from modules.summarizer.file_reader import read_docx, read_pdf_with_meta, read_txt

        text = ""
        title = "Student Practice Paper"
        page_count = None

        if request.content_type and "multipart/form-data" in request.content_type:
            file = request.files.get("file")
            if not file or not file.filename:
                return _err("No file uploaded")
            filename = file.filename
            title = f"Paper — {filename}"
            lower = filename.lower()
            if lower.endswith(".pdf"):
                pdf_meta = read_pdf_with_meta(file)
                text = pdf_meta["text"]
                page_count = pdf_meta["pageCount"]
                if not text.strip():
                    return _err(
                        f"PDF has {page_count} pages but no extractable text. "
                        "Scanned/image PDFs need OCR first — try pasting text or a text-based PDF."
                    )
            elif lower.endswith(".docx"):
                text = read_docx(file)
            elif lower.endswith(".txt"):
                text = read_txt(file)
            else:
                return _err("Only PDF, DOCX, and TXT allowed")
            counts = {
                "mcq": int(request.form.get("mcq") or 0),
                "short": int(request.form.get("short") or 0),
                "long": int(request.form.get("long") or 0),
            }
        else:
            body = _json_body()
            text = (body.get("text") or "").strip()
            counts = body.get("counts") or {}
            counts = {
                "mcq": int(counts.get("mcq") or 0),
                "short": int(counts.get("short") or 0),
                "long": int(counts.get("long") or 0),
            }

        text = (text or "").strip()
        if not text:
            return _err("Upload a file or paste notes (at least a short paragraph).")

        max_paste = 350_000
        if not (request.content_type and "multipart/form-data" in request.content_type):
            if len(text) > max_paste:
                return _err(
                    f"Pasted text is too long ({len(text):,} characters). "
                    f"Maximum is {max_paste:,}. Upload a file or paste a smaller section."
                )

        if request.content_type and "multipart/form-data" in request.content_type:
            meta = {
                "examTitle": request.form.get("examTitle"),
                "subject": request.form.get("subject"),
                "studentName": request.form.get("studentName"),
                "rollNo": request.form.get("rollNo"),
                "className": request.form.get("className"),
                "duration": request.form.get("duration"),
                "date": request.form.get("date"),
            }
        else:
            meta = body.get("meta") or {}

        paper = generate_paper_from_notes(
            text,
            counts,
            title=title,
            meta={k: v for k, v in meta.items() if v},
            page_count=page_count,
        )
        return _ok(paper)
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc), 500)


@questionbank_bp.route("/api/questionbank/papers/generate", methods=["POST"])
def papers_generate():
    db = _db()
    try:
        body = _json_body()
        paper = generate_paper(db, body)
        return _ok(paper)
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc), 500)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/papers/save", methods=["POST"])
def papers_save():
    db = _db()
    try:
        body = _json_body()
        paper = body.get("paper") or body
        title = body.get("title") or paper.get("title")
        filters = body.get("filters") or {}
        user_id = body.get("userId") or body.get("user_id")
        module = (body.get("module") or "questionbank").strip()
        mode = (body.get("mode") or filters.get("mode") or "").strip()
        if user_id is not None:
            try:
                user_id = int(user_id)
            except (TypeError, ValueError):
                user_id = None
        paper_id = save_paper(
            db, title, paper, filters, user_id=user_id, module=module, mode=mode
        )
        from modules.activity_log import try_log

        try_log(module, "paper_saved", {"paperId": paper_id, "title": title, "mode": mode}, user_id)
        return _ok({"id": paper_id})
    except Exception as exc:
        return _err(str(exc), 500)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/papers", methods=["GET"])
def papers_list():
    db = _db()
    try:
        module = (request.args.get("module") or "questionbank").strip()
        user_id = request.args.get("userId") or request.args.get("user_id")
        limit = min(int(request.args.get("limit") or 50), 200)
        q = db.query(SavedPaper).order_by(SavedPaper.id.desc())
        if module:
            q = q.filter(SavedPaper.module == module)
        if user_id:
            try:
                q = q.filter(SavedPaper.user_id == int(user_id))
            except (TypeError, ValueError):
                pass
        rows = q.limit(limit).all()
        items = []
        for row in rows:
            filters = {}
            paper = {}
            try:
                filters = json.loads(row.filters_json or "{}")
            except json.JSONDecodeError:
                pass
            try:
                paper = json.loads(row.payload_json or "{}")
            except json.JSONDecodeError:
                pass
            q_count = sum(
                len(sec.get("questions") or [])
                for sec in (paper.get("sections") or [])
            )
            items.append(
                {
                    "id": row.id,
                    "userId": row.user_id,
                    "module": row.module,
                    "mode": row.mode,
                    "title": row.title,
                    "filters": filters,
                    "questionCount": q_count,
                    "marks": paper.get("marks"),
                    "subtitle": (
                        f"{q_count} questions · {paper.get('marks') or '—'} marks"
                        if q_count
                        else (row.mode or filters.get("mode") or "")
                    ),
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
            )
        return _ok({"count": len(items), "items": items})
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/papers/<int:paper_id>", methods=["GET"])
def papers_get(paper_id):
    db = _db()
    try:
        row = db.query(SavedPaper).filter(SavedPaper.id == paper_id).first()
        if not row:
            return _err("Paper not found.", 404)
        paper = {}
        filters = {}
        try:
            paper = json.loads(row.payload_json or "{}")
        except json.JSONDecodeError:
            pass
        try:
            filters = json.loads(row.filters_json or "{}")
        except json.JSONDecodeError:
            pass
        return _ok(
            {
                "id": row.id,
                "userId": row.user_id,
                "module": row.module,
                "mode": row.mode,
                "title": row.title,
                "paper": paper,
                "filters": filters,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
        )
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/papers/clear", methods=["DELETE"])
def papers_clear():
    db = _db()
    try:
        module = (request.args.get("module") or "questionbank").strip()
        user_id = request.args.get("userId") or request.args.get("user_id")
        q = db.query(SavedPaper)
        if module:
            q = q.filter(SavedPaper.module == module)
        if user_id:
            try:
                q = q.filter(SavedPaper.user_id == int(user_id))
            except (TypeError, ValueError):
                pass
        deleted = q.delete(synchronize_session=False)
        db.commit()
        return _ok({"deleted": deleted})
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/papers/<int:paper_id>", methods=["DELETE"])
def papers_delete(paper_id):
    db = _db()
    try:
        row = db.query(SavedPaper).filter(SavedPaper.id == paper_id).first()
        if not row:
            return _err("Paper not found.", 404)
        db.delete(row)
        db.commit()
        return _ok({"deleted": paper_id})
    finally:
        db.close()


# ---------- Admin CRUD ----------


def _admin_list(model, serializer, order_field):
    db = _db()
    try:
        rows = db.query(model).order_by(order_field).all()
        return _ok([serializer(r) for r in rows])
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/boards", methods=["GET", "POST"])
def admin_boards():
    if request.method == "GET":
        return _admin_list(Board, board_dict, Board.name)
    body = _json_body()
    name = (body.get("name") or "").strip()
    code = (body.get("code") or "").strip().lower()
    if not name or not code:
        return _err("name and code required")
    db = _db()
    try:
        row = Board(name=name, code=code)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _ok(board_dict(row))
    except Exception as exc:
        db.rollback()
        return _err(str(exc))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/classes", methods=["GET", "POST"])
def admin_classes():
    if request.method == "GET":
        db = _db()
        try:
            rows = db.query(SchoolClass).options(joinedload(SchoolClass.board)).all()
            return _ok([class_dict(c) for c in rows])
        finally:
            db.close()
    body = _json_body()
    name = (body.get("name") or "").strip()
    if not name:
        return _err("name required")
    db = _db()
    try:
        row = SchoolClass(name=name, board_id=body.get("boardId"))
        db.add(row)
        db.commit()
        row = (
            db.query(SchoolClass)
            .options(joinedload(SchoolClass.board))
            .filter(SchoolClass.id == row.id)
            .first()
        )
        return _ok(class_dict(row))
    except Exception as exc:
        db.rollback()
        return _err(str(exc))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/exam-types", methods=["GET", "POST"])
def admin_exam_types():
    if request.method == "GET":
        return _admin_list(ExamType, exam_dict, ExamType.name)
    body = _json_body()
    name = (body.get("name") or "").strip()
    code = (body.get("code") or "").strip().lower()
    if not name or not code:
        return _err("name and code required")
    db = _db()
    try:
        row = ExamType(name=name, code=code)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _ok(exam_dict(row))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/subjects", methods=["GET", "POST"])
def admin_subjects():
    if request.method == "GET":
        return _admin_list(Subject, subject_dict, Subject.name)
    body = _json_body()
    name = (body.get("name") or "").strip()
    if not name:
        return _err("name required")
    db = _db()
    try:
        row = Subject(name=name)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _ok(subject_dict(row))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/books", methods=["GET", "POST"])
def admin_books():
    if request.method == "GET":
        db = _db()
        try:
            rows = (
                db.query(Book)
                .options(joinedload(Book.subject))
                .join(Subject)
                .filter(Subject.name != "English")
                .order_by(Book.class_level, Book.name)
                .all()
            )
            from .service import find_book_pdf_path

            return _ok(
                [
                    {
                        **book_dict(b),
                        "hasPdfOnDisk": bool(find_book_pdf_path(b.id)),
                    }
                    for b in rows
                ]
            )
        finally:
            db.close()
    body = _json_body()
    name = (body.get("name") or "").strip()
    subject_id = body.get("subjectId")
    class_level = body.get("classLevel")
    if not name or not subject_id:
        return _err("name and subjectId required")
    db = _db()
    try:
        row = Book(
            name=name,
            subject_id=subject_id,
            class_level=int(class_level) if class_level is not None else None,
        )
        db.add(row)
        db.commit()
        row = (
            db.query(Book)
            .options(joinedload(Book.subject))
            .filter(Book.id == row.id)
            .first()
        )
        return _ok(book_dict(row))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/books/ensure", methods=["POST"])
def admin_ensure_book():
    """Find or create book by name + subject + class (flexible admin upload)."""
    body = _json_body()
    name = (body.get("name") or "").strip()
    subject_id = body.get("subjectId")
    subject_name = (body.get("subjectName") or "").strip()
    class_level = body.get("classLevel")
    if not name:
        return _err("Book name required.")
    try:
        class_level = int(class_level) if class_level is not None else None
    except (TypeError, ValueError):
        class_level = None
    db = _db()
    try:
        if not subject_id and subject_name:
            sub = db.query(Subject).filter(Subject.name == subject_name).first()
            if not sub:
                sub = Subject(name=subject_name)
                db.add(sub)
                db.flush()
            subject_id = sub.id
        if not subject_id:
            return _err("Subject name required (e.g. Physics, Biology).")
        q = db.query(Book).filter(Book.name == name, Book.subject_id == subject_id)
        if class_level is not None:
            q = q.filter(Book.class_level == class_level)
        existing = q.first()
        if existing:
            row = (
                db.query(Book)
                .options(joinedload(Book.subject))
                .filter(Book.id == existing.id)
                .first()
            )
            return _ok(book_dict(row), message="Existing book — PDF will update this record.")
        row = Book(name=name, subject_id=subject_id, class_level=class_level)
        db.add(row)
        db.commit()
        row = (
            db.query(Book)
            .options(joinedload(Book.subject))
            .filter(Book.id == row.id)
            .first()
        )
        return _ok(book_dict(row), message="New book created.")
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/classes/<int:class_id>", methods=["DELETE"])
def admin_delete_class(class_id):
    db = _db()
    try:
        row = db.query(SchoolClass).filter(SchoolClass.id == class_id).first()
        if not row:
            return _err("Class not found", 404)
        db.delete(row)
        db.commit()
        return _ok({"deleted": class_id})
    except Exception as exc:
        db.rollback()
        return _err(str(exc))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/exam-types/<int:exam_id>", methods=["DELETE"])
def admin_delete_exam(exam_id):
    db = _db()
    try:
        row = db.query(ExamType).filter(ExamType.id == exam_id).first()
        if not row:
            return _err("Exam type not found", 404)
        db.query(PaperPattern).filter(PaperPattern.exam_type_id == exam_id).delete()
        db.delete(row)
        db.commit()
        return _ok({"deleted": exam_id})
    except Exception as exc:
        db.rollback()
        return _err(str(exc))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/subjects/<int:subject_id>", methods=["DELETE"])
def admin_delete_subject(subject_id):
    db = _db()
    try:
        row = db.query(Subject).filter(Subject.id == subject_id).first()
        if not row:
            return _err("Subject not found", 404)
        books = db.query(Book).filter(Book.subject_id == subject_id).all()
        for book in books:
            db.query(Chapter).filter(Chapter.book_id == book.id).delete()
            db.delete(book)
        db.delete(row)
        db.commit()
        return _ok({"deleted": subject_id})
    except Exception as exc:
        db.rollback()
        return _err(str(exc))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/books/<int:book_id>", methods=["DELETE"])
def admin_delete_book(book_id):
    from .service import delete_book_pdf_files

    db = _db()
    try:
        row = db.query(Book).filter(Book.id == book_id).first()
        if not row:
            return _err("Book not found", 404)
        name = row.name
        pdfs_removed = delete_book_pdf_files(book_id)
        db.query(Chapter).filter(Chapter.book_id == book_id).delete()
        db.delete(row)
        db.commit()
        return _ok(
            {"deleted": book_id, "bookName": name, "pdfsRemoved": pdfs_removed},
            message=f"{name} cleared (chapters + PDF on server).",
        )
    except Exception as exc:
        db.rollback()
        return _err(str(exc))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/patterns/<int:pattern_id>", methods=["DELETE"])
def admin_delete_pattern(pattern_id):
    db = _db()
    try:
        row = db.query(PaperPattern).filter(PaperPattern.id == pattern_id).first()
        if not row:
            return _err("Pattern not found", 404)
        db.delete(row)
        db.commit()
        return _ok({"deleted": pattern_id})
    except Exception as exc:
        db.rollback()
        return _err(str(exc))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/chapters/upload", methods=["POST"])
def admin_chapter_upload():
    """Upload chapter PDF — text extracted and saved to database."""
    import traceback
    from pathlib import Path

    from modules.summarizer.file_reader import read_pdf_from_path

    book_id = request.form.get("bookId", type=int)
    title = (request.form.get("title") or "").strip() or "Full Book"
    file = request.files.get("file")
    if not book_id:
        return _err("Select a book first (Load Punjab Board setup if list is empty).")
    if not file or not file.filename:
        return _err("PDF file required")

    lower = file.filename.lower()
    if not lower.endswith(".pdf"):
        return _err("Only PDF files are supported")

    uploads_dir = Path(__file__).resolve().parents[2] / "uploads" / "books"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in file.filename)
    save_path = uploads_dir / f"book{book_id}_{safe_name}"

    try:
        file.save(save_path)
    except Exception as exc:
        return _err(f"Could not save PDF file: {exc}")

    quick = (request.form.get("quick") or "true").lower() != "false"

    try:
        meta = read_pdf_from_path(
            save_path,
            max_pages=500,
            max_chars=2_000_000,
            ocr_fallback=not quick,
        )
        text = (meta.get("text") or "").strip()
    except Exception as exc:
        if quick:
            text = ""
            meta = {"method": "pending_ocr", "pageCount": 0}
        else:
            return _err(f"Could not read PDF: {exc}")

    db = _db()
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            return _err("Book not found. Refresh page and select book again.")

        needs_ocr = len(text) < 30
        if needs_ocr and quick:
            existing_fb = (
                db.query(Chapter)
                .filter(Chapter.book_id == book_id, Chapter.title == title)
                .first()
            )
            if not existing_fb:
                save_full_book_text(db, book_id, "", title=title)
            elif (existing_fb.content_text or "").strip():
                pass
            return _ok(
                {
                    "needsOcr": True,
                    "pdfSaved": str(save_path.name),
                    "bookName": book.name,
                    "message": "PDF saved on server. OCR step required.",
                },
                message=f"PDF saved for {book.name}. OCR will run next — keep tab open.",
            )

        if len(text) < 30:
            return _err(
                "Could not extract text from PDF. Set GEMINI_API_KEY in backend/.env for scanned books."
            )

        row = save_full_book_text(db, book_id, text, title=title)
        split_info = split_book_into_chapters(db, book_id, text)

        note = ""
        if meta.get("truncated"):
            note = (
                f" Large PDF — read {meta.get('pagesRead')}/{meta.get('pageCount')} pages."
            )
        if meta.get("ocrUsed"):
            note += " Scanned PDF — OCR applied."
        if split_info.get("created") or split_info.get("updated"):
            note += f" {split_info['message']}"
        elif not split_info.get("created") and not split_info.get("updated"):
            note += " Chapters not auto-detected — Full Book saved; AI will still build questions."

        ch_count = len(split_info.get("titles") or [])
        return _ok(
            {
                **chapter_dict(row, include_content=True),
                "pdfSaved": str(save_path.name),
                "charCount": len(text),
                "pageCount": meta.get("pageCount"),
                "pagesRead": meta.get("pagesRead"),
                "truncated": bool(meta.get("truncated")),
                "ocrUsed": bool(meta.get("ocrUsed")),
                "extractMethod": meta.get("method"),
                "bookName": book.name,
                "chaptersSplit": ch_count or split_info.get("created", 0),
                "chapterTitles": split_info.get("titles") or [],
                "readyForGenerate": True,
            },
            message=f"Book saved for {book.name}.{note}",
        )
    except ValueError as exc:
        db.rollback()
        return _err(str(exc))
    except Exception as exc:
        db.rollback()
        traceback.print_exc()
        return _err(
            f"Database save failed: {exc}. "
            "If Physics book is very large, try uploading one chapter PDF at a time."
        )
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/books/<int:book_id>/process-pdf", methods=["POST"])
def admin_book_process_pdf(book_id):
    """OCR/extract text from PDF already saved on server, then split chapters."""
    db = _db()
    try:
        result = process_book_pdf(db, book_id, use_ocr=True)
        n = len(result.get("split", {}).get("titles") or [])
        return _ok(
            result,
            message=f"Text extracted — {n} chapters. Now build questions.",
        )
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc), 500)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/books/<int:book_id>/status", methods=["GET"])
def admin_book_status(book_id):
    """Chapter + question counts per book (debug)."""
    from .service import find_book_pdf_path

    db = _db()
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            return _err("Book not found", 404)
        fb = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.title == "Full Book")
            .first()
        )
        chapters = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.title != "Full Book")
            .order_by(Chapter.sort_order)
            .all()
        )
        if not chapters:
            chapters = (
                db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.sort_order).all()
            )
        qmap = question_counts_for_chapters(db, [c.id for c in chapters])
        rows = [
            {
                "title": c.title,
                "charCount": len(c.content_text or ""),
                "questionCount": qmap.get(c.id, 0),
            }
            for c in chapters
        ]
        pdf_path = find_book_pdf_path(book_id)
        with_text = sum(1 for c in chapters if len(c.content_text or "") > 80)
        return _ok(
            {
                "bookId": book_id,
                "bookName": book.name,
                "chapters": rows,
                "chapterCount": len([c for c in chapters if c.title != "Full Book"]) or len(rows),
                "chaptersWithText": with_text,
                "fullBookChars": len(fb.content_text or "") if fb else 0,
                "totalQuestions": sum(qmap.values()),
                "pdfOnServer": bool(pdf_path),
                "pdfFile": pdf_path.name if pdf_path else None,
                "readyForTeacher": with_text > 0,
            }
        )
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/books/<int:book_id>/resplit-chapters", methods=["POST"])
def admin_book_resplit(book_id):
    """Re-split saved Full Book text into all chapters (e.g. fix 5 → 11)."""
    db = _db()
    try:
        split_info = resplit_book_chapters(db, book_id)
        n = len(split_info.get("titles") or [])
        return _ok(split_info, message=f"Re-split into {n} chapters.")
    except ValueError as exc:
        return _err(str(exc))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/books/<int:book_id>/generate-questions", methods=["POST"])
def admin_book_generate_questions(book_id):
    """Generate MCQ/short/long questions for all chapters of a book (AI)."""
    body = _json_body()
    db = _db()
    try:
        kwargs = {}
        if body.get("mcqPerChapter") is not None:
            kwargs["mcq_per"] = int(body["mcqPerChapter"])
        if body.get("shortPerChapter") is not None:
            kwargs["short_per"] = int(body["shortPerChapter"])
        if body.get("longPerChapter") is not None:
            kwargs["long_per"] = int(body["longPerChapter"])
        kwargs["force"] = bool(body.get("force", False))
        kwargs["only_missing"] = bool(body.get("onlyMissing", not kwargs["force"]))
        result = bulk_generate_for_book(db, book_id, **kwargs)
        errors = [c for c in result.get("chapters") or [] if c.get("error")]
        msg = f"Done — {result['totalGenerated']} questions in database."
        if errors:
            msg += f" {len(errors)} chapter(s) failed — see API Log."
        return _ok(result, message=msg)
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc), 500)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/chapters", methods=["GET", "POST"])
def admin_chapters():
    if request.method == "GET":
        db = _db()
        try:
            book_id = request.args.get("bookId", type=int)
            query = db.query(Chapter).options(joinedload(Chapter.questions))
            if book_id:
                query = query.filter(Chapter.book_id == book_id)
            rows = query.order_by(Chapter.sort_order, Chapter.title).all()
            named = [c for c in rows if c.title != "Full Book"]
            if named:
                rows = named
            from .content_clean import book_text_usable

            qmap = question_counts_for_chapters(db, [c.id for c in rows])
            out = []
            for c in rows:
                row = chapter_dict(c, question_count=qmap.get(c.id, 0))
                ok, reason = book_text_usable(c.content_text or "", min_words=30)
                row["textQuality"] = "ok" if ok else reason
                out.append(row)
            return _ok(out)
        finally:
            db.close()

    body = _json_body()
    title = (body.get("title") or "").strip()
    book_id = body.get("bookId")
    if not title or not book_id:
        return _err("title and bookId required")
    db = _db()
    try:
        existing = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.title == title)
            .first()
        )
        if existing:
            existing.content_text = body.get("contentText") or ""
            if "sortOrder" in body:
                existing.sort_order = int(body.get("sortOrder") or 0)
            row = existing
        else:
            row = Chapter(
                book_id=book_id,
                title=title,
                content_text=body.get("contentText") or "",
                sort_order=int(body.get("sortOrder") or 0),
            )
            db.add(row)
        db.commit()
        db.refresh(row)

        split_info = None
        gen_info = None
        if title == "Full Book" and (row.content_text or "").strip():
            split_info = split_book_into_chapters(db, book_id, row.content_text)
            if body.get("autoGenerate", True):
                try:
                    gen_info = bulk_generate_for_book(db, book_id)
                except Exception as gen_exc:
                    gen_info = {"error": str(gen_exc), "totalGenerated": 0}

        payload = chapter_dict(row, include_content=True)
        if split_info:
            payload["chaptersSplit"] = split_info.get("created", 0)
            payload["chapterTitles"] = split_info.get("titles") or []
        if gen_info:
            payload["questionsGenerated"] = gen_info.get("totalGenerated", 0)
        return _ok(payload)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/chapters/<int:chapter_id>", methods=["GET", "PUT", "DELETE"])
def admin_chapter_detail(chapter_id):
    db = _db()
    try:
        row = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not row:
            return _err("Chapter not found", 404)
        if request.method == "DELETE":
            title = row.title
            db.delete(row)
            db.commit()
            return _ok({"deleted": chapter_id, "title": title}, message="Chapter removed")
        if request.method == "GET":
            return _ok(chapter_dict(row, include_content=True))
        body = _json_body()
        if "title" in body:
            row.title = body["title"].strip()
        if "contentText" in body:
            row.content_text = body["contentText"]
        if "sortOrder" in body:
            row.sort_order = int(body["sortOrder"])
        db.commit()
        return _ok(chapter_dict(row, include_content=True))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/patterns", methods=["GET", "POST"])
def admin_patterns():
    if request.method == "GET":
        db = _db()
        try:
            rows = (
                db.query(PaperPattern)
                .options(
                    joinedload(PaperPattern.board),
                    joinedload(PaperPattern.exam_type),
                )
                .all()
            )
            return _ok([pattern_dict(p) for p in rows])
        finally:
            db.close()
    body = _json_body()
    board_id = body.get("boardId")
    exam_type_id = body.get("examTypeId")
    if not board_id or not exam_type_id:
        return _err("boardId and examTypeId required")
    db = _db()
    try:
        row = PaperPattern(
            board_id=board_id,
            exam_type_id=exam_type_id,
            mcq_count=int(body.get("mcqCount") or 15),
            short_count=int(body.get("shortCount") or 10),
            long_count=int(body.get("longCount") or 5),
            total_marks=int(body.get("totalMarks") or 100),
            duration=body.get("duration") or "3 Hours",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _ok(pattern_dict(row))
    except Exception as exc:
        db.rollback()
        return _err(str(exc))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/chapters/<int:chapter_id>/generate", methods=["POST"])
def admin_generate_questions(chapter_id):
    body = _json_body()
    db = _db()
    try:
        result = generate_for_chapter(
            db,
            chapter_id,
            mcq=int(body.get("mcqCount") or 3),
            short=int(body.get("shortCount") or 2),
            long=int(body.get("longCount") or 1),
            use_n8n=bool(body.get("useN8n")),
        )
        return _ok(result)
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc), 500)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/webhook/n8n/questions", methods=["POST"])
def n8n_webhook_questions():
    body = _json_body()
    chapter_id = body.get("chapterId")
    questions = body.get("questions") or []
    if not chapter_id:
        return _err("chapterId required")
    db = _db()
    try:
        result = import_n8n_questions(db, int(chapter_id), questions)
        return _ok(result)
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc), 500)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/import-questions", methods=["POST"])
def admin_import_questions():
    """Paste JSON from n8n, Gemini, or manual export — saves to database."""
    body = _json_body()
    chapter_id = body.get("chapterId")
    questions = body.get("questions") or []
    if not chapter_id:
        return _err("chapterId required")
    if not questions:
        return _err("questions array required")
    db = _db()
    try:
        result = import_n8n_questions(db, int(chapter_id), questions)
        return _ok(result)
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc), 500)
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/questions", methods=["POST"])
def admin_add_question():
    body = _json_body()
    chapter_id = body.get("chapterId")
    qtype = (body.get("questionType") or "").lower()
    text = (body.get("questionText") or "").strip()
    if not chapter_id or not qtype or not text:
        return _err("chapterId, questionType, questionText required")
    db = _db()
    try:
        row = Question(
            chapter_id=chapter_id,
            question_type=qtype,
            question_text=text,
            options_json=json.dumps(body.get("options") or []),
            correct_answer=body.get("correctAnswer") or "",
            difficulty=body.get("difficulty") or "medium",
            source="manual",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _ok(question_dict(row))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/questions/<int:question_id>", methods=["DELETE"])
def admin_delete_question(question_id):
    db = _db()
    try:
        row = db.query(Question).filter(Question.id == question_id).first()
        if not row:
            return _err("Not found", 404)
        db.delete(row)
        db.commit()
        return _ok({"deleted": question_id})
    finally:
        db.close()
