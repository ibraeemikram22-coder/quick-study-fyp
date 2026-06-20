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


@app.route("/api/health", methods=["GET"])
def health():
    return {
        "ok": True,
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