from flask import Blueprint, jsonify, request

from .service import get_tool

grammar_bp = Blueprint("grammar", __name__)


@grammar_bp.route("/check", methods=["POST"])
def check_grammar():
    try:
        data = request.get_json() or {}
        text = data.get("text")
        if not text:
            return jsonify({"error": "text is required"}), 400

        tool = get_tool()
        matches = tool.check(text)
        corrected = tool.correct(text)

        errors = []
        for err in matches:
            msg = err.message.lower()
            if "agreement" in msg:
                reason = "Subject and verb agreement issue."
            elif "tense" in msg:
                reason = "Incorrect verb tense."
            elif "spelling" in msg:
                reason = "Spelling mistake."
            elif "infinitive" in msg:
                reason = "Base form of verb is required after 'to'."
            else:
                reason = "General grammar improvement needed."

            errors.append(
                {
                    "message": err.message,
                    "offset": err.offset,
                    "length": err.error_length,
                    "suggestions": err.replacements,
                    "explanation": reason,
                }
            )

        from modules.activity_log import try_log
        from modules.record_storage import save_module_record
        from modules.request_user import user_id_from_request

        user_id = user_id_from_request()
        result = {
            "corrected": corrected,
            "error_count": len(matches),
            "errors": errors,
            "original": text[:2000],
        }
        record_id = save_module_record(
            "grammar",
            f"Grammar check ({len(matches)} errors)",
            text,
            result,
            user_id=user_id,
            meta={"errorCount": len(matches)},
        )
        try_log(
            "grammar",
            "checked",
            {"recordId": record_id, "errorCount": len(matches)},
            user_id,
        )

        return jsonify(
            {
                "id": record_id,
                "corrected": corrected,
                "error_count": len(matches),
                "errors": errors,
            }
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
