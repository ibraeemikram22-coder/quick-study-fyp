import os
import uuid

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from .youtube import download_audio, fetch_youtube_transcript, extract_video_id
from .gemini_transcribe import transcribe_media_file
from .whisper_model import get_transcript, whisper_available
from .storage import save_transcript, transcript_to_dict
from .transcript_cleaner import finalize_transcript
from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import TranscriptRecord
from modules.request_user import user_id_from_request as _user_id_from_request

transcript_bp = Blueprint("transcript", __name__)

UPLOAD_DIR = os.path.join("temp", "uploads")
ALLOWED_EXT = {".mp4", ".webm", ".mkv", ".mov", ".mp3", ".wav", ".m4a", ".ogg"}
MAX_UPLOAD = 20 * 1024 * 1024


def _is_youtube_url(url: str) -> bool:
    u = (url or "").lower()
    return "youtube.com" in u or "youtu.be" in u


def _ok(transcript, source, *, input_type="youtube", source_label=""):
    transcript = finalize_transcript(transcript)
    words = len(transcript.split())
    from modules.activity_log import try_log

    user_id = _user_id_from_request()
    record_id = save_transcript(
        transcript,
        user_id=user_id,
        input_type=input_type,
        source_label=source_label,
        source_engine=source,
        word_count=words,
    )
    try_log(
        "transcript",
        "generated",
        {"recordId": record_id, "source": source, "wordCount": words, "inputType": input_type},
        user_id,
    )
    return jsonify({
        "success": True,
        "id": record_id,
        "transcript": transcript,
        "source": source,
        "wordCount": words,
    })


def _fail(code, message, status=400):
    return jsonify({
        "success": False,
        "error": code,
        "message": message,
        "transcript": message,
    }), status


def _transcribe_file(path: str):
    try:
        return transcribe_media_file(path), "gemini"
    except RuntimeError:
        if whisper_available():
            return get_transcript(path), "whisper"
        raise


@transcript_bp.route("/generate", methods=["POST"])
def generate_transcript():
    try:
        if request.files and request.files.get("video"):
            return _handle_upload(request.files["video"])

        data = request.get_json(silent=True) or {}
        url = (data.get("text") or data.get("url") or "").strip()

        if not url:
            return _fail("missing_input", "Paste a YouTube link or upload a video file.")

        if _is_youtube_url(url):
            return _handle_youtube(url)

        if extract_video_id(url):
            return _handle_youtube(f"https://www.youtube.com/watch?v={extract_video_id(url)}")

        return _fail(
            "invalid_url",
            "Only YouTube links or video file upload are supported.",
        )

    except RuntimeError as exc:
        return _fail("transcription_failed", str(exc), 500)
    except Exception as exc:
        return _fail("server_error", f"Error: {exc}", 500)


def _handle_upload(file_storage):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = secure_filename(file_storage.filename or "video.mp4")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXT:
        return _fail(
            "invalid_file",
            f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXT))}",
        )

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_UPLOAD:
        return _fail("file_too_large", "File too large. Maximum size is 20 MB.")

    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
    file_storage.save(path)

    try:
        text, source = _transcribe_file(path)
        if not text or len(text.split()) < 2:
            return _fail("empty", "No speech detected in this file.")
        return _ok(
            text,
            source,
            input_type="upload",
            source_label=file_storage.filename or "uploaded file",
        )
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _handle_youtube(url: str):
    text, err_code, err_msg = fetch_youtube_transcript(url)

    if text:
        return _ok(text, "youtube_captions", input_type="youtube", source_label=url)

    if err_code == "copyright":
        return _fail("copyright", err_msg)

    if err_code in ("restricted", "blocked", "unplayable", "invalid_url"):
        return _fail(err_code, err_msg or "Cannot access this video.")

    try:
        audio_path = download_audio(url)
        text, source = _transcribe_file(audio_path)
        if text and len(text.split()) >= 2:
            return _ok(text, source, input_type="youtube", source_label=url)
        return _fail("empty", "No speech could be transcribed from this video.")
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()
        if any(k in low for k in ("copyright", "blocked", "private", "unavailable")):
            return _fail(
                "copyright",
                "Copyright or access restriction: YouTube blocked downloading audio "
                "for this video. Try another video or upload your own file.",
            )
        if "GEMINI_API_KEY" in msg:
            return _fail(
                "config",
                "Add GEMINI_API_KEY in backend/.env to transcribe videos without subtitles.",
                500,
            )
        return _fail("transcription_failed", msg, 500)


@transcript_bp.route("/history", methods=["GET"])
def transcript_history():
    init_db()
    limit = min(int(request.args.get("limit") or 30), 100)
    user_id = request.args.get("userId") or request.args.get("user_id")
    db = SessionLocal()
    try:
        q = db.query(TranscriptRecord).order_by(TranscriptRecord.id.desc())
        if user_id:
            try:
                q = q.filter(TranscriptRecord.user_id == int(user_id))
            except (TypeError, ValueError):
                pass
        rows = q.limit(limit).all()
        return jsonify(
            {
                "success": True,
                "count": len(rows),
                "items": [transcript_to_dict(r) for r in rows],
            }
        )
    finally:
        db.close()


@transcript_bp.route("/history/<int:record_id>", methods=["GET"])
def transcript_get(record_id):
    init_db()
    db = SessionLocal()
    try:
        row = db.query(TranscriptRecord).filter(TranscriptRecord.id == record_id).first()
        if not row:
            return jsonify({"success": False, "error": "Transcript not found"}), 404
        return jsonify({"success": True, "data": transcript_to_dict(row, include_text=True)})
    finally:
        db.close()
