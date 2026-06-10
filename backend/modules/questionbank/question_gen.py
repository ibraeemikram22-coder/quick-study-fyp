import json
import os
import random
import re
import time
import uuid

import requests

from modules.gemini_config import (
    RETRYABLE_STATUSES as RETRYABLE,
    SKIP_MODEL_STATUSES,
    gemini_model_chain,
    gemini_url as _gemini_url,
)

# Gemini context budget for question generation (characters)
MAX_CONTENT_CHARS = int(os.getenv("QUESTION_GEN_MAX_CHARS", "220000"))
NUM_SAMPLE_WINDOWS = 8


def _call_gemini_json(prompt, api_key, temperature=0.88):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": temperature,
            "topP": 0.95,
        },
    }
    last_err = "Gemini unavailable"
    for model in gemini_model_chain():
        for attempt, wait in enumerate((0, 2, 4)):
            if wait:
                time.sleep(wait)
            try:
                res = requests.post(
                    _gemini_url(model),
                    params={"key": api_key},
                    json=body,
                    timeout=180,
                )
            except requests.RequestException as exc:
                last_err = str(exc)
                continue
            if res.ok:
                data = res.json()
                parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts") or []
                text = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p) for p in parts
                ).strip()
                if not text:
                    last_err = "Empty Gemini response"
                    continue
                return _parse_json(text)
            if res.status_code in SKIP_MODEL_STATUSES:
                last_err = res.text[:200]
                break
            if res.status_code not in RETRYABLE:
                raise RuntimeError(f"Gemini error ({res.status_code}): {res.text[:200]}")
            last_err = res.text[:200]
    raise RuntimeError(
        "Could not generate questions (Gemini busy). Wait 1 minute and try again."
    )


def _parse_json(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            return json.loads(match.group())
        raise RuntimeError("AI returned invalid JSON.")


def _clean_mcq_option(opt, index: int) -> str:
    """Strip duplicate A)/B) prefixes — UI adds (A), (B) labels."""
    s = str(opt or "").strip()
    s = re.sub(r"^\(?[A-Da-d]\)?[.):\-\s]+", "", s)
    s = re.sub(r"^[A-Da-d]\s+", "", s)
    if re.fullmatch(r"[A-Da-d]", s):
        return f"Option {index + 1}"
    return s or f"Option {index + 1}"


def _normalize_questions(items):
    allowed = {"mcq", "short", "long"}
    out = []
    for item in items:
        qtype = (item.get("questionType") or item.get("type") or "").lower().strip()
        if qtype not in allowed:
            continue
        text = (item.get("questionText") or item.get("question") or "").strip()
        if not text:
            continue
        options = item.get("options") or []
        if not isinstance(options, list):
            options = []
        if qtype == "mcq":
            options = [_clean_mcq_option(o, i) for i, o in enumerate(options[:4])]
        out.append(
            {
                "questionType": qtype,
                "questionText": text,
                "options": options,
                "correctAnswer": str(item.get("correctAnswer") or "").strip(),
                "difficulty": (item.get("difficulty") or "medium").lower(),
            }
        )
    return out


def _detect_content_language(content_text: str) -> str:
    """Return 'urdu' when source is primarily Arabic/Urdu script."""
    text = content_text or ""
    arabic_script = sum(
        1
        for c in text
        if "\u0600" <= c <= "\u06FF"
        or "\u0750" <= c <= "\u077F"
        or "\u08A0" <= c <= "\u08FF"
    )
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    if arabic_script >= 30 or (arabic_script > 0 and arabic_script >= latin * 0.25):
        return "urdu"
    return "english"


def _language_instruction(lang: str) -> str:
    if lang == "urdu":
        return (
            "The source content is in Urdu. Write ALL questionText, options, and correctAnswer "
            "values in proper Urdu script (اردو رسم الخط). "
            "Do NOT use Roman Urdu or English transliteration (e.g. avoid 'kya hai', 'sawal', 'jawab'). "
            "Use native Urdu/Arabic script only, matching the style of the source material."
        )
    return (
        "Write all questions in the same language as the source content. "
        "If the source is English, use clear English."
    )


def _content_for_questions(content_text: str, max_chars: int = MAX_CONTENT_CHARS):
    """
    Use full text when it fits. For large documents, pick random windows spread
    across the whole file so each generate run covers different parts.
    """
    content = (content_text or "").strip()
    total = len(content)
    if total <= max_chars:
        return content, total, total, False, {
            "windows": 1,
            "coveragePercent": 100,
            "coverageNote": "Full document used for questions.",
        }

    rng = random.Random()
    window_size = max(8000, max_chars // NUM_SAMPLE_WINDOWS)
    span = max(0, total - window_size)

    positions = []
    for i in range(NUM_SAMPLE_WINDOWS):
        base = int(span * (i + 0.5) / NUM_SAMPLE_WINDOWS) if span else 0
        jitter = rng.randint(-window_size // 3, window_size // 3) if span else 0
        positions.append(max(0, min(span, base + jitter)))

    positions = sorted(set(positions))
    parts = []
    for pos in positions:
        pct = int(100 * pos / total) if total else 0
        chunk = content[pos : pos + window_size]
        parts.append(f"[--- excerpt from ~{pct}% through the document ---]\n\n{chunk}")

    merged = "\n\n".join(parts)
    if len(merged) > max_chars:
        merged = merged[:max_chars]

    coverage_pct = min(100, round(100 * len(merged) / total)) if total else 0
    return merged, total, len(merged), True, {
        "windows": len(positions),
        "coveragePercent": coverage_pct,
        "coverageNote": (
            f"Large document ({total:,} characters): {len(positions)} different sections "
            f"sampled this time (~{coverage_pct}% of text). "
            "Generate again to get questions from other parts."
        ),
    }


def generate_questions_from_content(
    chapter_title,
    content_text,
    mcq_count=3,
    short_count=2,
    long_count=1,
    page_count=None,
):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY missing in backend/.env")

    content = (content_text or "").strip()
    if len(content) < 30:
        raise ValueError("Chapter content is too short. Paste at least a paragraph.")

    content_slice, total_chars, used_chars, truncated, coverage = _content_for_questions(content)
    content_lang = _detect_content_language(content)
    batch_id = uuid.uuid4().hex[:8]

    focus_hints = [
        "definitions, key terms, and vocabulary",
        "cause-and-effect and explanations",
        "examples, case studies, and applications",
        "comparisons, lists, and classifications",
        "dates, names, formulas, and factual details",
        "main themes and chapter summaries",
    ]
    rng = random.Random()
    focus_pick = rng.sample(focus_hints, k=min(3, len(focus_hints)))

    prompt = f"""You are a school exam question writer for Pakistan boards.
Create questions ONLY from the chapter content below. Return JSON only.

LANGUAGE (mandatory):
{_language_instruction(content_lang)}

VARIETY (mandatory — batch {batch_id}):
- This is a NEW paper generation. Create completely FRESH questions — do NOT repeat common textbook phrasing.
- Spread questions across ALL excerpt sections below (early, middle, and late parts of the document).
- Emphasize these angles this time: {", ".join(focus_pick)}.
- Vary difficulty and question wording. No two questions should feel like duplicates.

{{
  "questions": [
    {{
      "questionType": "mcq",
      "questionText": "...",
      "options": ["first option text only", "second option", "third option", "fourth option"],
      "correctAnswer": "B",
      "difficulty": "easy|medium|hard"
    }},
    {{
      "questionType": "short",
      "questionText": "...",
      "options": [],
      "correctAnswer": "model answer",
      "difficulty": "medium"
    }},
    {{
      "questionType": "long",
      "questionText": "...",
      "options": [],
      "correctAnswer": "model answer outline",
      "difficulty": "hard"
    }}
  ]
}}

Counts required:
- exactly {mcq_count} mcq
- exactly {short_count} short
- exactly {long_count} long

Rules for MCQ options:
- Each option is ONLY the answer text (no "A)", "B)", "C)" prefix — the app adds labels).
- correctAnswer must be a single letter A, B, C, or D.

Cover important topics from across ALL excerpts below — every section must contribute at least one question.

Chapter title: {chapter_title}

Content:
{content_slice}
"""

    data = _call_gemini_json(prompt, api_key)
    questions = data.get("questions") or []
    if not questions:
        raise RuntimeError("AI returned no questions.")
    normalized = _normalize_questions(questions)
    return normalized, {
        "totalCharacters": total_chars,
        "usedCharacters": used_chars,
        "truncated": truncated,
        "contentLanguage": content_lang,
        "pageCount": page_count,
        "coveragePercent": coverage.get("coveragePercent"),
        "sampleWindows": coverage.get("windows"),
        "coverageNote": coverage.get("coverageNote"),
        "generationBatch": batch_id,
    }


def trigger_n8n_webhook(chapter_id, chapter_title, content_text, counts):
    url = (os.getenv("N8N_QUESTION_WEBHOOK_URL") or "").strip()
    if not url:
        raise ValueError(
            "N8N_QUESTION_WEBHOOK_URL not set. Add it to backend/.env or use built-in AI."
        )

    callback = (os.getenv("QUESTIONBANK_PUBLIC_URL") or "http://localhost:3000").rstrip(
        "/"
    )
    payload = {
        "chapterId": chapter_id,
        "chapterTitle": chapter_title,
        "contentText": content_text,
        "counts": counts,
        "callbackUrl": f"{callback}/api/questionbank/webhook/n8n/questions",
    }
    res = requests.post(url, json=payload, timeout=60)
    if not res.ok:
        raise RuntimeError(f"n8n webhook failed ({res.status_code}): {res.text[:200]}")
    try:
        return res.json()
    except ValueError:
        return {"status": "sent", "raw": res.text[:500]}
