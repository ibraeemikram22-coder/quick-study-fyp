import os
import time

import requests

from modules.gemini_config import (
    RETRYABLE_STATUSES as RETRYABLE,
    SKIP_MODEL_STATUSES,
    format_gemini_failure,
    gemini_model_chain,
    gemini_post,
    gemini_url as _gemini_url,
)


def _call_gemini(prompt, api_key):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    last_err = "Gemini unavailable"

    for model in gemini_model_chain():
        for attempt, wait in enumerate((0, 2, 4)):
            if wait:
                time.sleep(wait)
            try:
                res = gemini_post(_gemini_url(model), api_key, body, timeout=90)
            except requests.RequestException as exc:
                last_err = str(exc)
                continue

            if res.ok:
                data = res.json()
                parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts") or []
                text = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p) for p in parts
                ).strip()
                if text:
                    return text
                last_err = "Empty Gemini response"
                continue

            if res.status_code in SKIP_MODEL_STATUSES:
                last_err = res.text[:200]
                break
            if res.status_code not in RETRYABLE:
                raise RuntimeError(format_gemini_failure(res.status_code, res.text))
            last_err = res.text[:200]

    raise RuntimeError(
        "Gemini is busy or unavailable. Wait a minute and try again."
    )


def humanize_text(text, convert_notes=False):
    from modules.gemini_config import format_gemini_failure, gemini_api_keys

    keys = gemini_api_keys()
    if not keys:
        raise ValueError("GEMINI_API_KEY missing in backend/.env")
    api_key = keys[0]

    prompt = f"""Rewrite this text naturally like a human wrote it.

Rules:
- Keep same meaning
- Remove robotic tone
- Make it conversational
- Improve readability

Text:
{text}
"""

    if convert_notes:
        prompt += "\nConvert into bullet points."

    return _call_gemini(prompt, api_key)
