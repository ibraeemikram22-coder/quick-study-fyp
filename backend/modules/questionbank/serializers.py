import json

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


def _dt(value):
    return value.isoformat() if value else None


def board_dict(row: Board):
    return {"id": row.id, "name": row.name, "code": row.code}


def class_dict(row: SchoolClass):
    return {
        "id": row.id,
        "name": row.name,
        "gradeLevel": row.grade_level,
        "boardId": row.board_id,
        "boardName": row.board.name if row.board else None,
    }


def exam_dict(row: ExamType):
    return {
        "id": row.id,
        "name": row.name,
        "code": row.code,
        "isEnabled": bool(row.is_enabled if row.is_enabled is not None else 1),
        "sortOrder": row.sort_order or 0,
    }


def subject_dict(row: Subject):
    return {"id": row.id, "name": row.name}


def book_dict(row: Book):
    return {
        "id": row.id,
        "name": row.name,
        "subjectId": row.subject_id,
        "subjectName": row.subject.name if row.subject else None,
        "classLevel": row.class_level,
    }


def chapter_dict(row: Chapter, include_content=False, question_count=None):
    if question_count is None:
        question_count = len(row.questions) if row.questions is not None else 0
    data = {
        "id": row.id,
        "bookId": row.book_id,
        "title": row.title,
        "sortOrder": row.sort_order,
        "questionCount": int(question_count or 0),
        "contentPreview": (row.content_text or "")[:120],
        "charCount": len(row.content_text or ""),
    }
    if include_content:
        data["contentText"] = row.content_text or ""
    return data


def pattern_dict(row: PaperPattern):
    return {
        "id": row.id,
        "boardId": row.board_id,
        "examTypeId": row.exam_type_id,
        "boardCode": row.board.code if row.board else None,
        "examCode": row.exam_type.code if row.exam_type else None,
        "mcqCount": row.mcq_count,
        "shortCount": row.short_count,
        "longCount": row.long_count,
        "shortAttempt": row.short_attempt,
        "longAttempt": row.long_attempt,
        "totalMarks": row.total_marks,
        "duration": row.duration,
    }


def question_dict(row: Question):
    options = []
    try:
        options = json.loads(row.options_json or "[]")
    except json.JSONDecodeError:
        options = []
    return {
        "id": row.id,
        "chapterId": row.chapter_id,
        "questionType": row.question_type,
        "questionText": row.question_text,
        "options": options,
        "correctAnswer": row.correct_answer,
        "difficulty": row.difficulty,
        "source": row.source,
        "createdAt": _dt(row.created_at),
    }


def paper_dict(row: SavedPaper):
    return {
        "id": row.id,
        "title": row.title,
        "payload": json.loads(row.payload_json or "{}"),
        "filters": json.loads(row.filters_json or "{}"),
        "createdAt": _dt(row.created_at),
    }
