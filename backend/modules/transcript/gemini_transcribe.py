import base64
import mimetypes
import os
import time

import requests

from modules.gemini_config import (
    RETRYABLE_STATUSES,
    SKIP_MODEL_STATUSES,
    gemini_model_chain,
    gemini_url,
)

MAX_MEDIA_BYTES = 20 * 1024 * 1024


def _call_gemini_audio(prompt: str, mime_type: str, b64_data: str, api_key: str) -> str:
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": b64_data}},
                ]
            }
        ]
    }
    last_err = "Gemini unavailable"

    for model in gemini_model_chain():
        for attempt, wait in enumerate((0, 2, 4)):
            if wait:
                time.sleep(wait)
            try:
                res = requests.post(
                    gemini_url(model),
                    params={"key": api_key},
                    json=body,
                    timeout=180,
                )
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
                text = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in parts
                ).strip()
                if text:
                    return text
                last_err = "Empty Gemini response"
                continue

            if res.status_code in SKIP_MODEL_STATUSES:
                last_err = res.text[:200]
                break
            if res.status_code not in RETRYABLE_STATUSES:
                raise RuntimeError(
                    f"Gemini error ({res.status_code}): {res.text[:200]}"
                )
            last_err = res.text[:200]

    raise RuntimeError(
        "Gemini is busy or unavailable. Wait a minute and try again."
    )


def transcribe_media_file(path: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY missing in backend/.env — required to transcribe audio/video without subtitles."
        )

    size = os.path.getsize(path)
    if size > MAX_MEDIA_BYTES:
        raise RuntimeError(
            "File is too large (max 20 MB). Use a shorter clip or a video with YouTube subtitles."
        )

    mime, _ = mimetypes.guess_type(path)
    if not mime or not (
        mime.startswith("audio/") or mime.startswith("video/")
    ):
        ext = os.path.splitext(path)[1].lower()
        mime = {
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
        }.get(ext, "audio/mpeg")

    with open(path, "rb") as media:
        b64 = base64.standard_b64encode(media.read()).decode()

    from .transcript_cleaner import ROMAN_TRANSCRIPT_RULES

    prompt = (
        "Listen and transcribe this audio/video.\n"
        f"{ROMAN_TRANSCRIPT_RULES}\n"
        "Return ONLY the transcript lines in Roman script, nothing else."
    )
    return _call_gemini_audio(prompt, mime, b64, api_key)
