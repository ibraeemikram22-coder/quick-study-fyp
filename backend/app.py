from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.exceptions import RequestEntityTooLarge
import os

load_dotenv()

app = Flask(__name__)
# Student PDF uploads (large textbooks) — up to 80 MB
UPLOAD_LIMIT_MB = int(os.getenv("MAX_UPLOAD_MB", "80"))
app.config["MAX_CONTENT_LENGTH"] = UPLOAD_LIMIT_MB * 1024 * 1024
CORS(app)


@app.errorhandler(RequestEntityTooLarge)
@app.errorhandler(413)
def request_entity_too_large(_exc):
    return jsonify(
        {
            "success": False,
            "error": "file_too_large",
            "message": (
                f"File bahut bara hai — maximum {UPLOAD_LIMIT_MB} MB allowed hai. "
                f"Your file exceeds the {UPLOAD_LIMIT_MB} MB upload limit."
            ),
            "maxUploadMb": UPLOAD_LIMIT_MB,
            "tips": [
                "PDF compress karein (ilovepdf.com / smallpdf.com)",
                "Sirf 1–2 chapters upload karein, poori book ek sath nahi",
                "Ya chapter ka text neeche paste karein",
            ],
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

# Video transcript (YouTube + Whisper)
from modules.transcript.routes import transcript_bp
app.register_blueprint(transcript_bp, url_prefix="/transcript")

# Auth (users in same SQLite database)
from modules.auth_routes import auth_bp

app.register_blueprint(auth_bp)

# Question Bank + shared database
from modules.questionbank.routes import questionbank_bp
from modules.questionbank.db import database_info, init_db
from modules.questionbank.seed import run_seed

init_db()
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
            "transcript /transcript/generate",
            "questionbank /api/questionbank/*",
            "auth /api/auth/*",
            "contact /api/contact/*",
            "history /api/history/*",
            "admin /api/admin/*",
        ],
    }

if __name__ == "__main__":
    app.run(debug=True, port=3000)