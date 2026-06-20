"""Track daily Gemini API request usage (server-side only)."""
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
USAGE_FILE = _BASE / "data" / "gemini_usage.json"


def daily_quota_limit():
    return max(1, int(os.getenv("GEMINI_DAILY_QUOTA", "1500")))


def _load():
    if not USAGE_FILE.exists():
        return {}
    try:
        return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data):
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _today_key():
    return date.today().isoformat()


def record_request():
    """Increment today's request count after a successful Gemini call."""
    today = _today_key()
    data = _load()
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    data["count"] = int(data.get("count") or 0) + 1
    data["lastRequestAt"] = datetime.now().isoformat(timespec="seconds")
    _save(data)
    return get_usage()


def get_usage():
    """Return today's usage stats for admin UI."""
    today = _today_key()
    limit = daily_quota_limit()
    data = _load()
    if data.get("date") != today:
        used = 0
    else:
        used = int(data.get("count") or 0)
    remaining = max(0, limit - used)
    tomorrow = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
    return {
        "date": today,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "percentUsed": round(100 * used / limit, 1) if limit else 0,
        "quotaExceeded": used >= limit,
        "resetsAt": tomorrow.isoformat(timespec="seconds"),
        "lastRequestAt": data.get("lastRequestAt") if data.get("date") == today else None,
        "apiKeyConfigured": bool((os.getenv("GEMINI_API_KEY") or "").strip()),
        "backupKeys": len(
            [k for k in (os.getenv("GEMINI_API_KEYS") or "").split(",") if k.strip()]
        ),
    }
