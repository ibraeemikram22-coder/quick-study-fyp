import os
import smtplib
from email.mime.text import MIMEText

from flask import Blueprint, jsonify, request

from .storage import get_contact_email, load_feedback, save_feedback_entry

contact_bp = Blueprint("contact", __name__)


def _ok(data=None, **extra):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload)


def _err(message, code=400):
    return jsonify({"success": False, "error": message}), code


def _try_send_email(name, email, subject, message):
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    smtp_user = (os.getenv("SMTP_USER") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    to_addr = get_contact_email()
    if not smtp_host or not smtp_user or not smtp_pass:
        return False

    body = (
        f"New message — Quick Study Builder\n\n"
        f"Name: {name}\nEmail: {email}\nSubject: {subject}\n\n{message}\n"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[Quick Study] {subject}"
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg["Reply-To"] = email

    port = int(os.getenv("SMTP_PORT") or 587)
    with smtplib.SMTP(smtp_host, port, timeout=15) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())
    return True


@contact_bp.route("/api/contact/info", methods=["GET"])
def contact_info():
    return _ok({"contactEmail": get_contact_email(), "platform": "Quick Study Builder"})


@contact_bp.route("/api/contact/feedback", methods=["POST"])
def submit_feedback():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "Visitor").strip()
    email = (body.get("email") or "").strip()
    subject = (body.get("subject") or "feedback").strip()
    message = (body.get("message") or "").strip()
    rating = body.get("rating")

    if rating is not None:
        message = f"Rating: {rating}/5 stars\n\n{message}".strip()

    if len(message) < 3:
        return _err("Please write a message.")
    if email and "@" not in email:
        return _err("Please enter a valid email.")

    entry = save_feedback_entry(
        {
            "name": name or "Anonymous",
            "email": email or "not provided",
            "subject": subject,
            "message": message,
            "rating": rating,
        }
    )

    from modules.activity_log import try_log

    try_log("contact", "feedback_submitted", {"feedbackId": entry.get("id")})

    emailed = False
    try:
        emailed = _try_send_email(name, email or get_contact_email(), subject, message)
    except Exception:
        emailed = False

    return _ok(
        {
            "id": entry["id"],
            "message": "Thank you! Your message was received."
            + (" A copy was emailed to the admin." if emailed else ""),
            "emailed": emailed,
        }
    )


@contact_bp.route("/api/contact/feedback", methods=["GET"])
def list_feedback():
    rows = load_feedback()
    return _ok({"count": len(rows), "items": rows[-50:]})
