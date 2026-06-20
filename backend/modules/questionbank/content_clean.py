"""Remove PDF watermarks and detect unusable book text."""

import re

# Common pirated-textbook watermarks (Pakistan PDF sites)
_WATERMARK_RE = re.compile(
    r"|".join(
        [
            r"www\.educatedzone\.com",
            r"educatedzone\.com",
            r"this\s+book\s+is\s+uploaded\s+by",
            r"studyplusplus\.com\s*\([^)]*\)",
            r"studyplusplus\.com",
            r"\(study\+\+\)",
            r"study\+\+",
            r"plusplus\.com",
            r"https?://\S+",
            r"www\.\S+\.(com|org|net)\b",
        ]
    ),
    re.IGNORECASE,
)

_REPEAT_CHUNK = re.compile(r"(.{20,80}?)(?:\1){4,}", re.DOTALL)


def sanitize_book_text(text: str) -> str:
    """Strip watermarks and collapse whitespace."""
    if not text:
        return ""
    t = text.replace("\x00", " ")
    t = _WATERMARK_RE.sub(" ", t)
    t = _REPEAT_CHUNK.sub(r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _meaningful_words(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z\u0600-\u06FF]{3,}", text or "")
    stop = {
        "study",
        "plusplus",
        "plus",
        "com",
        "book",
        "uploaded",
        "www",
        "http",
        "https",
        "chapter",
        "unit",
        "the",
        "and",
        "for",
    }
    return [w for w in words if w.lower() not in stop and len(w) >= 3]


def book_text_usable(text: str, min_words: int = 45) -> tuple[bool, str]:
    """
    Return (ok, cleaned_text_or_reason).
    Rejects watermark-only PDFs that produce garbage questions.
    """
    raw = (text or "").strip()
    if len(raw) < 80:
        return False, "too_short"

    low = raw.lower()
    wm_hits = low.count("studyplusplus") + low.count("educatedzone") + low.count("(study++)")
    if wm_hits >= 3:
        cleaned_wm = sanitize_book_text(raw)
        wm_words = _meaningful_words(cleaned_wm)
        if len(wm_words) < min_words:
            return False, "watermark_only"

    cleaned = sanitize_book_text(raw)
    words = _meaningful_words(cleaned)

    if len(cleaned) < 100 or len(words) < min_words:
        if wm_hits >= 2 or len(words) < 15:
            return False, "watermark_only"
        return False, "too_short"

    # Highly repetitive garbage (same token repeated)
    if words:
        unique_ratio = len({w.lower() for w in words}) / len(words)
        if unique_ratio < 0.12 and len(words) > 30:
            return False, "repetitive_garbage"

    return True, cleaned


def require_usable_text(text: str, book_label: str = "Book") -> str:
    ok, result = book_text_usable(text)
    if ok:
        return result
    messages = {
        "watermark_only": (
            f"{book_label}: PDF contains only watermarks (studyplusplus / educatedzone). "
            "Upload an official watermark-free PDF, then run Fix Chapters."
        ),
        "repetitive_garbage": (
            f"{book_label}: text could not be read. Re-upload a clean official PDF and run Fix Chapters."
        ),
        "too_short": (
            f"{book_label}: chapter text is too short. Upload the PDF, run OCR if needed, then Fix Chapters."
        ),
    }
    raise ValueError(messages.get(result, f"{book_label}: usable book text not found."))
