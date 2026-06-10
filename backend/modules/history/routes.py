import json

from flask import Blueprint, jsonify, request

from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import ActivityLog, SavedPaper

history_bp = Blueprint("history", __name__)


def _ok(data=None, **extra):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload)


def _err(message, code=400):
    return jsonify({"success": False, "error": message}), code


def log_activity(user_id, module, action, details=None):
    from modules.activity_log import try_log

    return try_log(module, action, details, user_id)


def _activity_dict(row):
    details = {}
    try:
        details = json.loads(row.details_json or "{}")
    except json.JSONDecodeError:
        pass
    return {
        "id": row.id,
        "userId": row.user_id,
        "module": row.module,
        "action": row.action,
        "details": details,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _paper_summary(row):
    filters = {}
    try:
        filters = json.loads(row.filters_json or "{}")
    except json.JSONDecodeError:
        pass
    return {
        "id": row.id,
        "userId": row.user_id,
        "module": row.module,
        "mode": row.mode,
        "title": row.title,
        "filters": filters,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@history_bp.route("/api/history/log", methods=["POST"])
def history_log():
    body = request.get_json(silent=True) or {}
    module = (body.get("module") or "").strip()
    action = (body.get("action") or "").strip()
    if not module or not action:
        return _err("module and action are required.")

    user_id = body.get("userId") or body.get("user_id")
    if user_id is not None:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            user_id = None

    log_id = log_activity(user_id, module, action, body.get("details") or {})
    return _ok({"id": log_id})


@history_bp.route("/api/history", methods=["GET"])
def history_list():
    init_db()
    module = (request.args.get("module") or "").strip()
    user_id = request.args.get("userId") or request.args.get("user_id")
    limit = min(int(request.args.get("limit") or 50), 200)

    db = SessionLocal()
    try:
        q = db.query(ActivityLog).order_by(ActivityLog.id.desc())
        if module:
            q = q.filter(ActivityLog.module == module)
        if user_id:
            try:
                q = q.filter(ActivityLog.user_id == int(user_id))
            except (TypeError, ValueError):
                pass
        rows = q.limit(limit).all()
        return _ok({"count": len(rows), "items": [_activity_dict(r) for r in rows]})
    finally:
        db.close()


@history_bp.route("/api/history/papers", methods=["GET"])
def history_papers():
    init_db()
    module = (request.args.get("module") or "questionbank").strip()
    user_id = request.args.get("userId") or request.args.get("user_id")
    limit = min(int(request.args.get("limit") or 50), 200)

    db = SessionLocal()
    try:
        q = db.query(SavedPaper).order_by(SavedPaper.id.desc())
        if module:
            q = q.filter(SavedPaper.module == module)
        if user_id:
            try:
                q = q.filter(SavedPaper.user_id == int(user_id))
            except (TypeError, ValueError):
                pass
        rows = q.limit(limit).all()
        return _ok({"count": len(rows), "items": [_paper_summary(r) for r in rows]})
    finally:
        db.close()
