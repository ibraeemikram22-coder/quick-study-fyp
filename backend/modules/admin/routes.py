from flask import Blueprint, jsonify, request

from modules.questionbank.db import SessionLocal, database_info, init_db
from modules.questionbank.models import (
    ActivityLog,
    ContactFeedback,
    ModuleRecord,
    Question,
    SavedPaper,
    TranscriptRecord,
    User,
)
from modules.record_storage import record_to_dict
from modules.transcript.storage import transcript_to_dict

admin_bp = Blueprint("admin", __name__)


def _ok(data=None, **extra):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload)


@admin_bp.route("/api/admin/stats", methods=["GET"])
def admin_stats():
    init_db()
    db = SessionLocal()
    try:
        return _ok(
            {
                "database": database_info(),
                "users": db.query(User).count(),
                "students": db.query(User).filter(User.role == "student").count(),
                "teachers": db.query(User).filter(User.role == "teacher").count(),
                "admins": db.query(User).filter(User.role == "admin").count(),
                "questions": db.query(Question).count(),
                "savedPapers": db.query(SavedPaper).count(),
                "contactMessages": db.query(ContactFeedback).count(),
                "activityLogs": db.query(ActivityLog).count(),
                "transcripts": db.query(TranscriptRecord).count(),
                "moduleRecords": db.query(ModuleRecord).count(),
                "grammar": db.query(ModuleRecord).filter(ModuleRecord.module == "grammar").count(),
                "quiz": db.query(ModuleRecord).filter(ModuleRecord.module == "quiz").count(),
                "humanizer": db.query(ModuleRecord).filter(ModuleRecord.module == "humanizer").count(),
                "summarizer": db.query(ModuleRecord).filter(ModuleRecord.module == "summarizer").count(),
            }
        )
    finally:
        db.close()


@admin_bp.route("/api/admin/papers", methods=["GET"])
def admin_papers():
    init_db()
    limit = min(int(request.args.get("limit") or 50), 200)
    module = (request.args.get("module") or "").strip()
    db = SessionLocal()
    try:
        q = db.query(SavedPaper).order_by(SavedPaper.id.desc())
        if module:
            q = q.filter(SavedPaper.module == module)
        rows = q.limit(limit).all()
        return _ok(
            {
                "count": len(rows),
                "items": [
                    {
                        "id": r.id,
                        "userId": r.user_id,
                        "module": r.module,
                        "mode": r.mode,
                        "title": r.title,
                        "createdAt": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
            }
        )
    finally:
        db.close()


@admin_bp.route("/api/admin/records", methods=["GET"])
def admin_records():
    init_db()
    module = (request.args.get("module") or "").strip()
    limit = min(int(request.args.get("limit") or 50), 200)
    db = SessionLocal()
    try:
        q = db.query(ModuleRecord).order_by(ModuleRecord.id.desc())
        if module:
            q = q.filter(ModuleRecord.module == module)
        rows = q.limit(limit).all()
        return _ok(
            {
                "count": len(rows),
                "items": [record_to_dict(r) for r in rows],
            }
        )
    finally:
        db.close()


@admin_bp.route("/api/admin/records/<int:record_id>", methods=["GET"])
def admin_record_detail(record_id):
    init_db()
    db = SessionLocal()
    try:
        row = db.query(ModuleRecord).filter(ModuleRecord.id == record_id).first()
        if not row:
            return jsonify({"success": False, "error": "Record not found"}), 404
        return _ok(record_to_dict(row, include_result=True))
    finally:
        db.close()


@admin_bp.route("/api/admin/transcripts", methods=["GET"])
def admin_transcripts():
    init_db()
    limit = min(int(request.args.get("limit") or 50), 200)
    db = SessionLocal()
    try:
        rows = (
            db.query(TranscriptRecord)
            .order_by(TranscriptRecord.id.desc())
            .limit(limit)
            .all()
        )
        return _ok(
            {
                "count": len(rows),
                "items": [transcript_to_dict(r) for r in rows],
            }
        )
    finally:
        db.close()


@admin_bp.route("/api/admin/transcripts/<int:record_id>", methods=["GET"])
def admin_transcript_detail(record_id):
    init_db()
    db = SessionLocal()
    try:
        row = db.query(TranscriptRecord).filter(TranscriptRecord.id == record_id).first()
        if not row:
            return jsonify({"success": False, "error": "Transcript not found"}), 404
        return _ok(transcript_to_dict(row, include_text=True))
    finally:
        db.close()


@admin_bp.route("/api/admin/users", methods=["GET"])
def admin_users():
    init_db()
    limit = min(int(request.args.get("limit") or 100), 500)
    db = SessionLocal()
    try:
        rows = db.query(User).order_by(User.id.desc()).limit(limit).all()
        return _ok(
            {
                "count": len(rows),
                "items": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "email": r.email,
                        "role": r.role,
                        "createdAt": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
            }
        )
    finally:
        db.close()
