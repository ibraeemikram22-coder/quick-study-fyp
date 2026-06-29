import os
import re
import time

import requests

from modules.gemini_config import (
    RETRYABLE_STATUSES,
    SKIP_MODEL_STATUSES,
    format_gemini_failure,
    gemini_model_chain,
    gemini_post,
    gemini_url,
    is_quota_exceeded,
)

BRACKET_TAG = re.compile(r"\[[^\]]{1,120}\]", re.UNICODE)
PAREN_SOUND = re.compile(
    r"\((?:music|singing|applause|laughter|instrumental)[^)]*\)",
    re.IGNORECASE | re.UNICODE,
)
NON_ROMAN_SCRIPT = re.compile(r"[\u0600-\u06FF\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F]")

ROMAN_TRANSCRIPT_RULES = """
STRICT RULES — ROMAN SCRIPT OUTPUT:
1. Use ONLY Latin letters (A-Z, a-z). Never use Devanagari (हिंदी), Urdu/Arabic script, or Gurmukhi.
2. VERBATIM — write exactly what is spoken or sung, in order. One phrase per line.
3. Hindi speech/lyrics → Roman Hindi (e.g. "be sir pair ki baatein kar raha hoon", NOT "बे सर पैर की").
4. Urdu speech/lyrics → Roman Urdu (e.g. "ghar ho kar bhi beghar phir raha hoon").
5. English speech → normal English spelling.
6. Do NOT translate Hindi/Urdu into English words — only transliterate to Roman.
7. Remove ONLY non-speech tags like [Music], (applause), ♪ — never remove real lyrics.
8. Do not summarize or skip lines.
"""


def strip_noise(text: str) -> str:
    if not text:
        return text
    text = BRACKET_TAG.sub("", text)
    text = PAREN_SOUND.sub("", text)
    text = re.sub(r"♪+", "", text)
    lines = []
    for line in text.replace("\r", "").split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    if lines:
        return "\n".join(lines)
    return re.sub(r"\s+", " ", text).strip()


def needs_roman_polish(text: str) -> bool:
    if not text:
        return False
    if BRACKET_TAG.search(text) or "[" in text:
        return True
    if NON_ROMAN_SCRIPT.search(text):
        return True
    return False


def _call_gemini_text(prompt: str, api_key: str) -> str:
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    last_err = "Gemini unavailable"

    for model in gemini_model_chain():
        for attempt, wait in enumerate((0, 2, 4)):
            if wait:
                time.sleep(wait)
            try:
                res = gemini_post(gemini_url(model), api_key, body, timeout=120)
            except requests.RequestException as exc:
                last_err = str(exc)
                continue

            if res.ok:
                data = res.json()
                parts = (
                    (data.get("candidates") or [{}])[0]
                    .get("content", {})
                    .get("parts")
                    or []
                )
                out = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in parts
                ).strip()
                if out:
                    return out
                last_err = "Empty Gemini response"
                continue

            if is_quota_exceeded(res.status_code, res.text):
                raise RuntimeError(format_gemini_failure(res.status_code, res.text))

            if res.status_code in SKIP_MODEL_STATUSES:
                last_err = res.text[:200]
                break
            if res.status_code not in RETRYABLE_STATUSES:
                raise RuntimeError(format_gemini_failure(res.status_code, res.text))
            last_err = res.text[:200]

    raise RuntimeError(last_err)


def _polish_chunk(snippet: str, api_key: str) -> str:
    prompt = f"""Convert this video transcript for a student learning tool.

{ROMAN_TRANSCRIPT_RULES}

Raw transcript (may be Hindi/Urdu script or mixed):
{snippet}

Return ONLY Roman-script verbatim lines. No headings, no explanation."""

    return strip_noise(_call_gemini_text(prompt, api_key))


def polish_roman_verbatim(text: str) -> str:
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return strip_noise(text)

    cleaned = strip_noise(text)
    chunk_size = 12000
    if len(cleaned) <= chunk_size:
        out = _polish_chunk(cleaned[:14000], api_key) or cleaned
    else:
        parts = []
        for start in range(0, len(cleaned), chunk_size):
            piece = cleaned[start : start + chunk_size]
            parts.append(_polish_chunk(piece, api_key) or piece)
            if start + chunk_size < len(cleaned):
                time.sleep(0.5)
        out = "\n".join(p for p in parts if p)

    if needs_roman_polish(out):
        raise RuntimeError(
            "Could not convert transcript to Roman script. "
            "Daily AI limit may be reached — please try again tomorrow."
        )
    return out or cleaned


def finalize_transcript(text: str) -> str:
    """Remove noise tags; output Roman Urdu/Hindi/English lines, verbatim."""
    stripped = strip_noise(text)
    if not needs_roman_polish(stripped):
        return stripped
    if not (os.getenv("GEMINI_API_KEY") or "").strip():
        return stripped
    return polish_roman_verbatim(stripped)
