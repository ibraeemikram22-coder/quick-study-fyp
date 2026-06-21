from flask import Blueprint, request, jsonify
from modules.humanizer.service import humanize_text

humanizer_bp = Blueprint("humanizer", __name__)

@humanizer_bp.route("/humanize", methods=["POST"])
def humanize():
    try:
        data = request.get_json()

        text = data.get("text")
        notes = data.get("notes", False)

        if not text:
            return jsonify({
                "error": "Text is required"
            }), 400

        result = humanize_text(text, notes)

        from modules.activity_log import try_log
        from modules.record_storage import save_module_record
        from modules.request_user import user_id_from_request

        user_id = user_id_from_request()
        record_id = save_module_record(
            "humanizer",
            "Humanized text",
            text,
            {"result": result, "notesMode": bool(notes)},
            user_id=user_id,
            meta={"chars": len(text or "")},
        )
        try_log(
            "humanizer",
            "humanized",
            {"recordId": record_id, "chars": len(text or "")},
            user_id,
        )

        return jsonify({"id": record_id, "result": result})

    except RuntimeError as e:
        msg = str(e)
        code = "quota_exceeded" if "quota" in msg.lower() or "429" in msg else "service_unavailable"
        return jsonify({"error": msg, "code": code}), 503
    except Exception as e:
        msg = str(e)
        code = "quota_exceeded" if "quota" in msg.lower() or "429" in msg else "service_error"
        return jsonify({"error": msg, "code": code}), 500