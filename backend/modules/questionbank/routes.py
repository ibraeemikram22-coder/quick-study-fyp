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
    generate_for_chapter,
    generate_paper,
    generate_paper_from_notes,
    import_n8n_questions,
    save_paper,
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


@questionbank_bp.route("/api/questionbank/seed", methods=["POST"])
def seed_data():
    created = run_seed()
    return _ok({"seeded": created, "message": "Sample data added" if created else "Already seeded"})


@questionbank_bp.route("/api/questionbank/metadata", methods=["GET"])
def metadata():
    db = _db()
    try:
        boards = [board_dict(b) for b in db.query(Board).order_by(Board.name).all()]
        classes = [class_dict(c) for c in db.query(SchoolClass).order_by(SchoolClass.name).all()]
        exams = [exam_dict(e) for e in db.query(ExamType).order_by(ExamType.name).all()]
        subjects = [subject_dict(s) for s in db.query(Subject).order_by(Subject.name).all()]
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


@questionbank_bp.route("/api/questionbank/books", methods=["GET"])
def list_books():
    db = _db()
    try:
        subject_id = request.args.get("subjectId", type=int)
        subject_name = request.args.get("subject")
        query = db.query(Book).options(joinedload(Book.subject))
        if subject_id:
            query = query.filter(Book.subject_id == subject_id)
        elif subject_name:
            sub = db.query(Subject).filter(Subject.name == subject_name).first()
            if not sub:
                return _ok([])
            query = query.filter(Book.subject_id == sub.id)
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
        query = db.query(Chapter).options(joinedload(Chapter.book))
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
        return _ok([chapter_dict(c) for c in rows])
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/pattern", methods=["GET"])
def get_pattern():
    db = _db()
    try:
        board_id = request.args.get("boardId", type=int)
        exam_id = request.args.get("examTypeId", type=int)
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
        return _ok(pattern_dict(row))
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


@questionbank_bp.route("/api/questionbank/student/export-docx", methods=["POST"])
def student_export_docx():
    """Download editable Word paper with aligned header."""
    try:
        from .paper_export import build_paper_docx

        body = _json_body()
        paper = body.get("paper")
        if not paper or not paper.get("sections"):
            return _err("paper with sections required")
        meta = body.get("meta") or {}
        include_key = bool(body.get("includeAnswerKey"))
        meta["includeAnswerKey"] = include_key
        blob = build_paper_docx(paper, meta)
        filename = (meta.get("examTitle") or "practice-paper").replace(" ", "-")[:40]
        return send_file(
            BytesIO(blob),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=f"{filename}.docx",
        )
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
            try:
                filters = json.loads(row.filters_json or "{}")
            except json.JSONDecodeError:
                pass
            items.append(
                {
                    "id": row.id,
                    "userId": row.user_id,
                    "module": row.module,
                    "mode": row.mode,
                    "title": row.title,
                    "filters": filters,
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
            rows = db.query(Book).options(joinedload(Book.subject)).all()
            return _ok([book_dict(b) for b in rows])
        finally:
            db.close()
    body = _json_body()
    name = (body.get("name") or "").strip()
    subject_id = body.get("subjectId")
    if not name or not subject_id:
        return _err("name and subjectId required")
    db = _db()
    try:
        row = Book(name=name, subject_id=subject_id)
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


@questionbank_bp.route("/api/questionbank/admin/chapters", methods=["GET", "POST"])
def admin_chapters():
    if request.method == "GET":
        db = _db()
        try:
            book_id = request.args.get("bookId", type=int)
            query = db.query(Chapter).options(joinedload(Chapter.questions))
            if book_id:
                query = query.filter(Chapter.book_id == book_id)
            rows = query.order_by(Chapter.sort_order).all()
            return _ok([chapter_dict(c) for c in rows])
        finally:
            db.close()

    body = _json_body()
    title = (body.get("title") or "").strip()
    book_id = body.get("bookId")
    if not title or not book_id:
        return _err("title and bookId required")
    db = _db()
    try:
        row = Chapter(
            book_id=book_id,
            title=title,
            content_text=body.get("contentText") or "",
            sort_order=int(body.get("sortOrder") or 0),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _ok(chapter_dict(row, include_content=True))
    finally:
        db.close()


@questionbank_bp.route("/api/questionbank/admin/chapters/<int:chapter_id>", methods=["GET", "PUT"])
def admin_chapter_detail(chapter_id):
    db = _db()
    try:
        row = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not row:
            return _err("Chapter not found", 404)
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
