"""Grammar check via Gemini when LanguageTool is unavailable (live server)."""
import json
import os
import re

import requests

from modules.gemini_config import (
    RETRYABLE_STATUSES,
    SKIP_MODEL_STATUSES,
    format_gemini_failure,
    gemini_api_keys,
    gemini_model_chain,
    gemini_post,
    gemini_url,
    record_successful_request,
)


def _parse_json(raw):
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _call_gemini(prompt, api_key):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    last_err = "Gemini unavailable"

    for model in gemini_model_chain():
        for wait in (0, 2, 4):
            if wait:
                import time

                time.sleep(wait)
            try:
                res = gemini_post(gemini_url(model), api_key, body, timeout=90)
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
                    p.get("text", "") if isinstance(p, dict) else str(p) for p in parts
                ).strip()
                if text:
                    record_successful_request()
                    return text
                last_err = "Empty Gemini response"
                continue

            if res.status_code in SKIP_MODEL_STATUSES:
                last_err = res.text[:200]
                break
            if res.status_code not in RETRYABLE_STATUSES:
                raise RuntimeError(format_gemini_failure(res.status_code, res.text))
            last_err = res.text[:200]

    raise RuntimeError(last_err)


def check_with_gemini(text):
    keys = gemini_api_keys()
    if not keys:
        raise RuntimeError(
            "GEMINI_API_KEY missing. Add a valid key in backend/.env on the server."
        )

    snippet = (text or "")[:6000]
    prompt = f"""You are an English grammar teacher. Fix grammar, spelling, and punctuation.

Return ONLY valid JSON (no markdown):
{{
  "corrected": "full corrected text",
  "error_count": 3,
  "errors": [
    {{
      "message": "short label",
      "offset": 0,
      "length": 4,
      "suggestions": ["fix"],
      "explanation": "one sentence why"
    }}
  ]
}}

Use real character offsets into the ORIGINAL text for offset/length.
Original text:
{snippet}
"""

    raw = _call_gemini(prompt, keys[0])
    data = _parse_json(raw)
    corrected = (data.get("corrected") or "").strip()
    errors = data.get("errors") or []
    if not corrected:
        raise RuntimeError("Grammar AI returned empty result.")
    return {
        "corrected": corrected,
        "error_count": int(data.get("error_count") or len(errors)),
        "errors": errors,
    }
