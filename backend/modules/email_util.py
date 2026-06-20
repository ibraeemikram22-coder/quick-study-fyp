import os
import smtplib
from email.mime.text import MIMEText


def smtp_configured() -> bool:
    return bool(
        (os.getenv("SMTP_HOST") or "").strip()
        and (os.getenv("SMTP_USER") or "").strip()
        and (os.getenv("SMTP_PASSWORD") or "").strip()
    )


def send_email(to_addr: str, subject: str, body: str) -> bool:
    """Send email via SMTP. Returns True if sent, False if SMTP not configured."""
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    smtp_user = (os.getenv("SMTP_USER") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    if not smtp_host or not smtp_user or not smtp_pass:
        return False

    to_addr = (to_addr or "").strip()
    if not to_addr:
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr

    port = int(os.getenv("SMTP_PORT") or 587)
    with smtplib.SMTP(smtp_host, port, timeout=20) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())
    return True


def send_teacher_verify_code(email: str, code: str, school_name: str = "") -> bool:
    school_line = f"\nSchool: {school_name}\n" if school_name else ""
    body = (
        "Quick Study Builder — Teacher verification\n\n"
        f"Your verification code is: {code}\n"
        f"{school_line}\n"
        "Enter this code on the login page to activate your teacher account.\n"
        "Code expires in 30 minutes.\n\n"
        "If you did not sign up, ignore this email."
    )
    return send_email(
        email,
        "[Quick Study] Teacher verification code",
        body,
    )
