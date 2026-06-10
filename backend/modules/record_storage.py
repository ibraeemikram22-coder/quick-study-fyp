import json

from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import ModuleRecord


def _preview(text, limit=400):
    t = (text or "").strip()
    return t[:limit] + ("…" if len(t) > limit else "")


def save_module_record(module, title, input_text, result_data, user_id=None, meta=None):
    init_db()
    db = SessionLocal()
    try:
        row = ModuleRecord(
            user_id=user_id,
            module=(module or "unknown")[:40],
            title=(title or "")[:300],
            input_preview=_preview(input_text, 500),
            result_json=json.dumps(result_data or {}, ensure_ascii=False),
            meta_json=json.dumps(meta or {}, ensure_ascii=False),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def record_to_dict(row, include_result=False):
    meta = {}
    try:
        meta = json.loads(row.meta_json or "{}")
    except json.JSONDecodeError:
        pass
    data = {
        "id": row.id,
        "userId": row.user_id,
        "module": row.module,
        "title": row.title,
        "inputPreview": row.input_preview,
        "meta": meta,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }
    if include_result:
        try:
            data["result"] = json.loads(row.result_json or "{}")
        except json.JSONDecodeError:
            data["result"] = {}
    else:
        try:
            result = json.loads(row.result_json or "{}")
            if isinstance(result, dict) and result.get("summary"):
                data["preview"] = _preview(result.get("summary"), 200)
            elif isinstance(result, dict) and result.get("corrected"):
                data["preview"] = _preview(result.get("corrected"), 200)
            elif isinstance(result, dict) and result.get("result"):
                data["preview"] = _preview(result.get("result"), 200)
            elif isinstance(result, list):
                data["preview"] = f"{len(result)} items"
            else:
                data["preview"] = _preview(str(result), 200)
        except json.JSONDecodeError:
            data["preview"] = ""
    return data
