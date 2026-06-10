from flask import request


def user_id_from_request():
    try:
        val = request.headers.get("X-User-Id")
        if val is None:
            body = request.get_json(silent=True) or {}
            val = body.get("userId") or body.get("user_id")
        if val is None and request.form:
            val = request.form.get("userId") or request.form.get("user_id")
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None
