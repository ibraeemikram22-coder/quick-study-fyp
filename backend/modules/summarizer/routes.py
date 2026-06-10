from flask import Blueprint, request, jsonify

from .file_reader import read_pdf, read_docx, read_txt
from .jobs import complete_job, create_job, fail_job, get_job, run_in_background, update_job
from .service import (
    FAST_MAX_CHARS,
    generate_summary,
    _clamp_bullets,
    _normalize_content_type,
    _normalize_output_language,
)


def _is_full_document(val):
    return str(val or "").lower() in ("1", "true", "yes", "on")

summarizer_bp = Blueprint("summarizer", __name__)


def _ok(payload):
    body = {
        "success": True,
        "summary": payload["summary"],
        "meta": payload["meta"],
        "insights": payload["insights"],
    }
    if payload.get("sections") is not None:
        body["sections"] = payload["sections"]
    if payload.get("chapterTitle"):
        body["chapterTitle"] = payload["chapterTitle"]
    return jsonify(body)


def _format_style(data, default="chapter"):
    style = (data.get("formatStyle") or default).strip().lower()
    return "bullets" if style == "bullets" else "chapter"


def _full_document_flag(value):
    return str(value or "").lower() in ("1", "true", "on", "yes")


def _save_summary_record(text, payload, kwargs):
    from modules.activity_log import try_log
    from modules.record_storage import save_module_record

    user_id = kwargs.get("user_id")
    title = kwargs.get("file_name") or "Text summary"
    record_id = save_module_record(
        "summarizer",
        title,
        text,
        payload,
        user_id=user_id,
        meta={
            "source": kwargs.get("source", "text"),
            "formatStyle": kwargs.get("format_style"),
            "async": kwargs.get("async_job", False),
        },
    )
    try_log(
        "summarizer",
        "generated",
        {"recordId": record_id, "chars": len(text or "")},
        user_id,
    )
    return record_id


_SUMMARY_GEN_KEYS = {
    "bullets",
    "source",
    "file_name",
    "format_style",
    "output_language",
    "content_type",
    "full_document",
    "quick_mode",
}


def _summary_gen_kwargs(kwargs):
    return {k: v for k, v in (kwargs or {}).items() if k in _SUMMARY_GEN_KEYS}


def _run_summarize_job(job_id, text, kwargs):
    def on_progress(pct, message):
        update_job(job_id, progress=pct, message=message)

    try:
        payload = generate_summary(
            text,
            progress_callback=on_progress,
            **_summary_gen_kwargs(kwargs),
        )
        record_id = _save_summary_record(text, payload, {**kwargs, "async_job": True})
        payload = {**payload, "recordId": record_id}
        complete_job(job_id, payload)
    except Exception as exc:
        fail_job(job_id, exc)
        raise


@summarizer_bp.route("/api/notes/job/<job_id>", methods=["GET"])
def get_summarize_job(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404
    body = {
        "success": True,
        "jobId": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
    }
    if job["status"] == "done" and job.get("result"):
        body["result"] = job["result"]
    if job["status"] == "error":
        body["error"] = job.get("error") or "Summarization failed"
    return jsonify(body)


@summarizer_bp.route("/api/notes/generate", methods=["POST"])
def summarize_text():
    try:
        data = request.get_json() or {}

        text = (data.get("text") or "").strip()
        bullets = _clamp_bullets(data.get("bulletCount", 5))

        if not text:
            return jsonify({"success": False, "error": "No text provided"}), 400

        style = _format_style(data)
        out_lang = _normalize_output_language(data.get("outputLanguage"))
        content = _normalize_content_type(data.get("contentType"))
        quick = _is_full_document(data.get("quickMode"))
        full_doc = not quick

        from modules.request_user import user_id_from_request

        user_id = user_id_from_request()

        if full_doc and len(text) > 3000:
            job_id = create_job()
            run_in_background(
                job_id,
                _run_summarize_job,
                text,
                {
                    "bullets": bullets,
                    "source": "text",
                    "format_style": style,
                    "output_language": out_lang,
                    "content_type": content,
                    "full_document": True,
                    "quick_mode": False,
                    "user_id": user_id,
                },
            )
            from modules.activity_log import try_log

            try_log(
                "summarizer",
                "job_started",
                {"jobId": job_id, "chars": len(text)},
                user_id,
            )
            return jsonify({"success": True, "jobId": job_id, "async": True})

        payload = generate_summary(
            text,
            bullets,
            source="text",
            format_style=style,
            output_language=out_lang,
            content_type=content,
            full_document=True,
            quick_mode=quick,
        )
        record_id = _save_summary_record(
            text,
            payload,
            {
                "source": "text",
                "format_style": style,
                "user_id": user_id,
                "async_job": False,
            },
        )
        response = {
            "success": True,
            "recordId": record_id,
            "summary": payload["summary"],
            "meta": payload["meta"],
            "insights": payload["insights"],
        }
        if payload.get("sections") is not None:
            response["sections"] = payload["sections"]
        if payload.get("chapterTitle"):
            response["chapterTitle"] = payload["chapterTitle"]
        return jsonify(response)

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@summarizer_bp.route("/api/notes/upload", methods=["POST"])
def summarize_file():
    try:
        file = request.files.get("file")

        if not file or not file.filename:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        bullets = _clamp_bullets(request.form.get("bulletCount", 5))
        style = (request.form.get("formatStyle") or "chapter").strip().lower()
        if style != "bullets":
            style = "chapter"
        filename = file.filename
        lower = filename.lower()

        if lower.endswith(".pdf"):
            text = read_pdf(file)
        elif lower.endswith(".docx"):
            text = read_docx(file)
        elif lower.endswith(".txt"):
            text = read_txt(file)
        else:
            return jsonify({
                "success": False,
                "error": "Only PDF, DOCX, and TXT allowed",
            }), 400

        text = (text or "").strip()
        if not text:
            return jsonify({
                "success": False,
                "error": (
                    "Could not read text from this file. "
                    "If it is a scanned PDF (image only), copy text manually into the paste box. "
                    "Or save as .txt / .docx with real text."
                ),
            }), 400

        out_lang = _normalize_output_language(request.form.get("outputLanguage"))
        content = _normalize_content_type(request.form.get("contentType"))
        quick = _is_full_document(request.form.get("quickMode"))
        kwargs = {
            "bullets": bullets,
            "source": "file",
            "file_name": filename,
            "format_style": style,
            "output_language": out_lang,
            "content_type": content,
            "full_document": True,
            "quick_mode": quick,
        }

        from modules.request_user import user_id_from_request

        kwargs["user_id"] = user_id_from_request()
        job_id = create_job()
        run_in_background(job_id, _run_summarize_job, text, kwargs)
        return jsonify({"success": True, "jobId": job_id, "async": True})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
