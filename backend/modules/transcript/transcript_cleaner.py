import os
import re
import time

import requests

from modules.gemini_config import (
    RETRYABLE_STATUSES,
    SKIP_MODEL_STATUSES,
    gemini_model_chain,
    gemini_url,
)

BRACKET_TAG = re.compile(r"\[[^\]]{1,120}\]", re.UNICODE)
PAREN_SOUND = re.compile(
    r"\((?:music|singing|applause|laughter|instrumental)[^)]*\)",
    re.IGNORECASE | re.UNICODE,
)
NON_ROMAN_SCRIPT = re.compile(r"[\u0600-\u06FF\u0900-\u097F\u0980-\u09FF]")

ROMAN_TRANSCRIPT_RULES = """
STRICT RULES:
1. ROMAN SCRIPT ONLY — use Latin letters (A-Z). Example: "tujhe dekh suna" NOT "तुझे देख" and NOT Urdu script.
2. VERBATIM — write exactly what is spoken/sung, in order. One phrase per line. Do not skip lines.
3. If the speaker uses Urdu or Hindi, write Roman Urdu/Hindi (transliteration). Do NOT translate into English words.
4. If the speaker uses English, write normal English.
5. Remove ONLY non-speech labels like [Music], [Singing], [संगीत], (applause), ♪ — never remove real lyrics.
6. Do not summarize, do not paraphrase, do not merge different lines.
7. If a chorus repeats in the audio, you may repeat that line when it is sung again.
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

            if res.status_code in SKIP_MODEL_STATUSES:
                last_err = res.text[:200]
                break
            if res.status_code not in RETRYABLE_STATUSES:
                raise RuntimeError(f"Gemini error ({res.status_code}): {res.text[:200]}")
            last_err = res.text[:200]

    raise RuntimeError(last_err)


def polish_roman_verbatim(text: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return strip_noise(text)

    snippet = strip_noise(text)[:14000]
    prompt = f"""Convert this video transcript for a student.

{ROMAN_TRANSCRIPT_RULES}

Raw transcript:
{snippet}

Return ONLY the Roman-script verbatim lines, nothing else."""

    try:
        return strip_noise(_call_gemini_text(prompt, api_key)) or strip_noise(text)
    except Exception:
        return strip_noise(text)


def finalize_transcript(text: str) -> str:
    """Remove noise tags; output Roman Urdu/English lines, verbatim."""
    stripped = strip_noise(text)
    if os.getenv("GEMINI_API_KEY"):
        return polish_roman_verbatim(stripped)
    return stripped
