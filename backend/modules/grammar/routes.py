from flask import Blueprint, jsonify, request

from .gemini_check import check_with_gemini
from .service import get_tool

grammar_bp = Blueprint("grammar", __name__)


def _lt_rate_limited(exc):
    msg = str(exc).lower()
    return "rate limit" in msg or "quota" in msg or "exceeded" in msg


@grammar_bp.route("/check", methods=["POST"])
def check_grammar():
    try:
        data = request.get_json() or {}
        text = data.get("text")
        if not text:
            return jsonify({"error": "text is required"}), 400

        import os

        use_gemini = os.getenv("PYTHONANYWHERE_SITE") or os.getenv("GRAMMAR_USE_GEMINI", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )

        if use_gemini:
            result = check_with_gemini(text)
            corrected = result["corrected"]
            errors = result["errors"]
            error_count = result["error_count"]
        else:
            try:
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
                error_count = len(matches)
            except Exception as exc:
                if _lt_rate_limited(exc):
                    result = check_with_gemini(text)
                    corrected = result["corrected"]
                    errors = result["errors"]
                    error_count = result["error_count"]
                else:
                    raise

        from modules.activity_log import try_log
        from modules.record_storage import save_module_record
        from modules.request_user import user_id_from_request

        user_id = user_id_from_request()
        result_payload = {
            "corrected": corrected,
            "error_count": error_count,
            "errors": errors,
            "original": text[:2000],
        }
        record_id = save_module_record(
            "grammar",
            f"Grammar check ({error_count} errors)",
            text,
            result_payload,
            user_id=user_id,
            meta={"errorCount": error_count},
        )
        try_log(
            "grammar",
            "checked",
            {"recordId": record_id, "errorCount": error_count},
            user_id,
        )

        return jsonify(
            {
                "id": record_id,
                "corrected": corrected,
                "error_count": error_count,
                "errors": errors,
            }
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
