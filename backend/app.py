from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Always load backend/.env (even if you run python from another folder)
load_dotenv(Path(__file__).resolve().parent / ".env")

app = Flask(__name__)
# Textbook PDF uploads — up to 120 MB per file
app.config["MAX_CONTENT_LENGTH"] = 120 * 1024 * 1024
CORS(app)


@app.errorhandler(413)
def request_entity_too_large(_exc):
    limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify(
        {
            "success": False,
            "error": (
                f"File too large (max {limit_mb} MB). Use a smaller or compressed PDF."
            ),
        }
    ), 413

# contact
from modules.contact.routes import contact_bp
from modules.contact.storage import import_feedback_json_to_db

app.register_blueprint(contact_bp)

# Grammar Route
from modules.grammar.routes import grammar_bp
app.register_blueprint(grammar_bp, url_prefix="/grammar")

# Quiz Route
from modules.quiz.routes import quiz_bp
app.register_blueprint(quiz_bp, url_prefix="/quiz")

# Humanizer Route
from modules.humanizer.routes import humanizer_bp
app.register_blueprint(humanizer_bp, url_prefix="/humanizer")

# Summarizer Route
from modules.summarizer.routes import summarizer_bp
app.register_blueprint(summarizer_bp)

# Video transcript (optional — heavy deps; paper/quiz modules work without it)
TRANSCRIPT_ENABLED = False
try:
    from modules.transcript.routes import transcript_bp

    app.register_blueprint(transcript_bp, url_prefix="/transcript")
    TRANSCRIPT_ENABLED = True
except ImportError as exc:
    print(f"[WARN] Transcript module disabled: {exc}")

# Auth (users in same SQLite database)
from modules.auth_routes import auth_bp

app.register_blueprint(auth_bp)

# Question Bank + shared database
from modules.questionbank.routes import questionbank_bp
from modules.questionbank.db import database_info, init_db
from modules.questionbank.seed import run_seed

init_db()
from modules.auth_bootstrap import ensure_admin_user

ensure_admin_user()
run_seed()
import_feedback_json_to_db()

app.register_blueprint(questionbank_bp)

# Activity / module history
from modules.history.routes import history_bp

app.register_blueprint(history_bp)

# Admin dashboard APIs
from modules.admin.routes import admin_bp

app.register_blueprint(admin_bp)

# Module history (grammar, quiz, humanizer, summarizer)
from modules.records.routes import records_bp

app.register_blueprint(records_bp)

@app.route("/")
def home():
    return "Quick Study Builder Backend Running"


def _ai_quota_payload(gemini_status):
    from modules.gemini_usage import get_usage

    usage = get_usage()
    status = str(gemini_status or "")
    google_exhausted = status == "error_429" or "429" in status
    internal_exhausted = bool(usage.get("quotaExceeded"))
    exhausted = google_exhausted or internal_exhausted
    return {
        "available": not exhausted and status == "ok",
        "exhausted": exhausted,
        "resetsAt": usage.get("resetsAt"),
        "used": usage.get("used"),
        "limit": usage.get("limit"),
        "message": (
            "Daily AI limit reached. Please try again tomorrow — "
            "AI tools will work automatically after the quota resets."
            if exhausted
            else None
        ),
    }


@app.route("/api/ping", methods=["GET"])
def ping():
    """Fast liveness check — no external API calls (used by frontend banner)."""
    return {"ok": True}


_GEMINI_HEALTH_CACHE = {"ts": 0.0, "status": "unknown"}


def _gemini_health_status(keys, cache_seconds=600):
    """Check Gemini key status; cache result to keep /api/health fast."""
    import time

    if not keys:
        return "missing"

    now = time.time()
    cached = _GEMINI_HEALTH_CACHE
    if cached["status"] != "unknown" and now - cached["ts"] < cache_seconds:
        return cached["status"]

    try:
        from modules.gemini_config import gemini_model_chain, gemini_post, gemini_url

        model = gemini_model_chain()[0]
        res = gemini_post(
            gemini_url(model),
            keys[0],
            {"contents": [{"parts": [{"text": "ok"}]}]},
            timeout=5,
        )
        status = "ok" if res.ok else f"error_{res.status_code}"
    except Exception as exc:
        status = f"error: {exc}"

    _GEMINI_HEALTH_CACHE.update(ts=now, status=status)
    return status


@app.route("/api/health", methods=["GET"])
def health():
    from flask import request

    from modules.gemini_config import gemini_api_keys

    keys = gemini_api_keys()
    if request.args.get("quick") == "1":
        gemini_status = _GEMINI_HEALTH_CACHE.get("status") or ("configured" if keys else "missing")
    else:
        gemini_status = _gemini_health_status(keys)

    return {
        "ok": True,
        "geminiKey": gemini_status,
        "aiQuota": _ai_quota_payload(gemini_status),
        "database": database_info(),
        "modules": [
            "grammar /grammar/check",
            "quiz /quiz/generate",
            "humanizer /humanizer/humanize",
            "summarizer /api/notes/*",
            *(
                ["transcript /transcript/generate"]
                if TRANSCRIPT_ENABLED
                else ["transcript (install yt-dlp + youtube-transcript-api)"]
            ),
            "questionbank /api/questionbank/*",
            "auth /api/auth/*",
            "contact /api/contact/*",
            "history /api/history/*",
            "admin /api/admin/*",
        ],
        "transcriptEnabled": TRANSCRIPT_ENABLED,
    }

if __name__ == "__main__":
    debug_flag = os.getenv("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes")
    app.run(debug=debug_flag, port=3000)