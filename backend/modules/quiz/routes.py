from flask import Blueprint, request, jsonify
import re

from modules.quiz.generator import generate_quiz_questions

quiz_bp = Blueprint("quiz", __name__)


def clean_text(text):
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@quiz_bp.route("/generate", methods=["POST"])
def generate_quiz():
    data = request.json or {}
    text = clean_text(data.get("text", ""))
    limit = int(data.get("limit", 5))

    questions = generate_quiz_questions(text, limit)

    from modules.activity_log import try_log
    from modules.record_storage import save_module_record
    from modules.request_user import user_id_from_request

    user_id = user_id_from_request()
    record_id = save_module_record(
        "quiz",
        f"Quiz ({len(questions)} questions)",
        text,
        {"questions": questions},
        user_id=user_id,
        meta={"limit": limit, "count": len(questions)},
    )
    try_log(
        "quiz",
        "generated",
        {"recordId": record_id, "count": len(questions), "limit": limit},
        user_id,
    )

    return jsonify({"id": record_id, "questions": questions})
