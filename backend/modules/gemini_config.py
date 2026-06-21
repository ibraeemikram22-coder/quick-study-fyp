"""Shared Gemini model IDs."""
import json
import os

DEFAULT_GEMINI_MODELS = (
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
)

RETRYABLE_STATUSES = {429, 500, 503, 504}
SKIP_MODEL_STATUSES = {404}
QUOTA_KEYWORDS = ("quota", "exceeded", "rate limit", "resource exhausted")


def gemini_api_keys():
    """Primary key + optional comma-separated backups (GEMINI_API_KEYS)."""
    keys = []
    primary = (os.getenv("GEMINI_API_KEY") or "").strip()
    extra = (os.getenv("GEMINI_API_KEYS") or "").strip()
    if primary:
        keys.append(primary)
    for k in extra.split(","):
        k = k.strip()
        if k and k not in keys:
            keys.append(k)
    return keys


def gemini_model_chain(env_key="GEMINI_MODEL"):
    override = (os.getenv(env_key) or "").strip()
    if override:
        rest = [m for m in DEFAULT_GEMINI_MODELS if m != override]
        return (override,) + tuple(rest)
    return DEFAULT_GEMINI_MODELS


def gemini_url(model):
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )


def _error_detail(response_text):
    try:
        payload = json.loads(response_text or "{}")
        err = payload.get("error") or {}
        return str(err.get("message") or response_text or "")
    except (json.JSONDecodeError, TypeError):
        return (response_text or "").strip()


def is_quota_exceeded(status_code, detail=""):
    text = (detail or "").lower()
    return status_code == 429 and any(k in text for k in QUOTA_KEYWORDS)


def record_successful_request():
    """Increment daily usage counter after a successful Gemini call."""
    try:
        from modules.gemini_usage import record_request

        return record_request()
    except Exception:
        return None


def check_daily_quota():
    """Raise RuntimeError when today's quota is exhausted."""
    from modules.gemini_usage import get_usage

    usage = get_usage()
    if usage.get("quotaExceeded"):
        raise RuntimeError(
            "Daily AI quota reached. Please try again tomorrow — your API key will work automatically."
        )
    return usage


def format_gemini_failure(status_code, response_text=""):
    detail = _error_detail(response_text)
    low = detail.lower()

    if is_quota_exceeded(status_code, detail) or status_code == 429:
        return "Daily AI quota reached. Please try again tomorrow."

    if status_code in (401, 403) or "api key" in low or "permission" in low or "invalid" in low:
        return (
            "Invalid or expired Gemini API key. Open PythonAnywhere → backend/.env → "
            "set a new GEMINI_API_KEY from Google AI Studio, then Reload the web app."
        )

    if status_code in RETRYABLE_STATUSES or "unavailable" in low or "high demand" in low:
        return "The AI service is temporarily unavailable. Please try again shortly."

    return "Something went wrong while generating content. Please try again."
