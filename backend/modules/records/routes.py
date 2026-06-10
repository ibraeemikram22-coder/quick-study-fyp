from flask import Blueprint, jsonify, request

from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import ModuleRecord
from modules.record_storage import record_to_dict

records_bp = Blueprint("records", __name__)


@records_bp.route("/api/records", methods=["GET"])
def list_records():
    init_db()
    module = (request.args.get("module") or "").strip()
    limit = min(int(request.args.get("limit") or 30), 100)
    user_id = request.args.get("userId") or request.args.get("user_id")
    db = SessionLocal()
    try:
        q = db.query(ModuleRecord).order_by(ModuleRecord.id.desc())
        if module:
            q = q.filter(ModuleRecord.module == module)
        if user_id:
            try:
                q = q.filter(ModuleRecord.user_id == int(user_id))
            except (TypeError, ValueError):
                pass
        rows = q.limit(limit).all()
        return jsonify(
            {
                "success": True,
                "count": len(rows),
                "items": [record_to_dict(r) for r in rows],
            }
        )
    finally:
        db.close()


@records_bp.route("/api/records/<int:record_id>", methods=["GET"])
def get_record(record_id):
    init_db()
    db = SessionLocal()
    try:
        row = db.query(ModuleRecord).filter(ModuleRecord.id == record_id).first()
        if not row:
            return jsonify({"success": False, "error": "Record not found"}), 404
        return jsonify({"success": True, "data": record_to_dict(row, include_result=True)})
    finally:
        db.close()
