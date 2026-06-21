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
    format_gemini_failure,
    gemini_api_keys,
    is_quota_exceeded,
    gemini_model_chain,
    gemini_post,
    gemini_url as _gemini_url,
)

# Gemini context budget for question generation (characters)
MAX_CONTENT_CHARS = int(os.getenv("QUESTION_GEN_MAX_CHARS", "220000"))
NUM_SAMPLE_WINDOWS = 8


def demo_fallback_enabled():
    """Off by default — when API fails, show error (no fake demo paper)."""
    return os.getenv("QUESTIONBANK_DEMO_FALLBACK", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _quota_error(exc):
    msg = str(exc or "").lower()
    return "quota" in msg or "rate limit" in msg or "429" in msg


def _demo_fallback_for_error(exc):
    """Use syllabus-based demo paper when Gemini/API is down (FYP presentation backup)."""
    if not demo_fallback_enabled():
        return False
    msg = str(exc or "").lower()
    if _quota_error(exc):
        return True
    hints = (
        "unavailable",
        "timed out",
        "timeout",
        "connection",
        "network",
        "refused",
        "503",
        "502",
        "500",
        "empty gemini",
        "invalid json",
        "no questions",
        "ssl",
        "name resolution",
    )
    return any(h in msg for h in hints)


def _sentences_from_text(text, min_len=35, max_len=240):
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    parts = re.split(r"(?<=[.!?؟])\s+", cleaned)
    out = [p.strip() for p in parts if min_len <= len(p.strip()) <= max_len]
    if not out and len(cleaned) > min_len:
        for i in range(0, min(len(cleaned), 12000), max_len):
            chunk = cleaned[i : i + max_len].strip()
            if len(chunk) >= min_len:
                out.append(chunk)
    return out


def _topics_from_text(text, chapter_title):
    topics = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or len(line) < 8:
            continue
        if re.match(r"^(chapter|unit|section|حصہ|باب)\s*[\d۰-۹]", line, re.I):
            topics.append(line[:140])
        elif re.match(r"^\d+[\).:\-]\s+\S", line):
            topics.append(line[:140])
    if chapter_title:
        topics.insert(0, chapter_title)
    seen = set()
    unique = []
    for t in topics:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique[:40]


def fallback_questions_from_content(
    chapter_title,
    content_text,
    mcq_count=0,
    short_count=0,
    long_count=0,
):
    """Rule-based questions from syllabus text when Gemini quota is unavailable."""
    from .content_clean import require_usable_text

    content_text = require_usable_text(content_text, chapter_title)
    sentences = _sentences_from_text(content_text)
    topics = _topics_from_text(content_text, chapter_title)
    if not sentences:
        raise ValueError("Book text too short. Admin → upload PDF → Fix Chapters.")

    rng = random.Random(time.time_ns())
    pool = sentences[:]
    rng.shuffle(pool)
    words_pool = []
    for s in pool:
        words_pool.extend(re.findall(r"[A-Za-z\u0600-\u06FF]{4,}", s))
    words_pool = list(dict.fromkeys(words_pool))[:80]

    items = []
    for i in range(int(mcq_count or 0)):
        sent = pool[i % len(pool)]
        key = rng.choice(words_pool) if words_pool else "concept"
        if key in sent and len(key) > 3:
            qtext = sent.replace(key, "________", 1)
        else:
            qtext = f"Which statement best matches the syllabus: \"{sent[:120]}\""
        distractors = rng.sample(words_pool, k=min(3, len(words_pool))) if words_pool else [
            "Option A",
            "Option B",
            "Option C",
        ]
        options = [key] + [d for d in distractors if d != key]
        while len(options) < 4:
            options.append(f"Alternative {len(options)}")
        options = options[:4]
        rng.shuffle(options)
        letter = chr(65 + options.index(key))
        items.append(
            {
                "questionType": "mcq",
                "questionText": qtext[:280] + ("?" if "?" not in qtext else ""),
                "options": options,
                "correctAnswer": letter,
                "difficulty": "medium",
            }
        )

    for i in range(int(short_count or 0)):
        topic = topics[i % len(topics)]
        sent = pool[(i + mcq_count) % len(pool)]
        items.append(
            {
                "questionType": "short",
                "questionText": f"Define or explain: {topic[:120]}",
                "options": [],
                "correctAnswer": sent[:200],
                "difficulty": "medium",
            }
        )

    for i in range(int(long_count or 0)):
        a = topics[i % len(topics)]
        b = topics[(i + 1) % len(topics)]
        items.append(
            {
                "questionType": "long",
                "questionText": (
                    f"(a) Write a detailed note on: {a[:100]}. (4)\n"
                    f"(b) Explain with examples: {b[:100]}. (4)"
                ),
                "options": [],
                "correctAnswer": "See syllabus — both parts from selected chapters.",
                "difficulty": "hard",
            }
        )

    return _normalize_questions(items), {
        "demoFallback": True,
        "coverageNote": "Demo mode: questions built from book text (Gemini quota unavailable).",
    }


def _call_gemini_json(prompt, api_key, temperature=0.88):
    try:
        from modules.gemini_config import check_daily_quota

        check_daily_quota()
    except RuntimeError:
        raise
    except Exception:
        pass

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": temperature,
            "topP": 0.95,
        },
    }
    keys = gemini_api_keys() or ([api_key] if api_key else [])
    if not keys:
        raise ValueError("GEMINI_API_KEY missing in backend/.env")

    last_err = "Gemini unavailable"
    for key_idx, use_key in enumerate(keys):
        for model in gemini_model_chain():
            for attempt, wait in enumerate((0, 3, 8)):
                if wait:
                    time.sleep(wait)
                try:
                    res = gemini_post(_gemini_url(model), use_key, body, timeout=180)
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
                    try:
                        from modules.gemini_config import record_successful_request

                        record_successful_request()
                    except Exception:
                        pass
                    return _parse_json(text)
                if res.status_code in SKIP_MODEL_STATUSES:
                    last_err = res.text[:200]
                    break
                if is_quota_exceeded(res.status_code, res.text):
                    last_err = format_gemini_failure(res.status_code, res.text)
                    break
                if res.status_code not in RETRYABLE:
                    raise RuntimeError(format_gemini_failure(res.status_code, res.text))
                last_err = format_gemini_failure(res.status_code, res.text)
        if key_idx + 1 < len(keys):
            time.sleep(1)
    raise RuntimeError(last_err or "Gemini unavailable. Wait 1–2 minutes and try again.")


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


def _language_instruction(lang: str, subject_name: str = "") -> str:
    subj = (subject_name or "").lower()
    is_computer = "computer" in subj
    lines = [
        "Use the EXACT wording and terminology from the Punjab Board textbook source.",
        "Do NOT translate, paraphrase, rephrase, or rewrite questions in a different language.",
        "If the book uses English technical terms (CPU, RAM, Algorithm, etc.), keep them in English exactly.",
        "If the book uses Urdu script for a topic, copy that Urdu text verbatim from the source.",
        "Extract questions from Review Questions, Exercises, and chapter content in official board exam style.",
        "Never convert English Computer/Science terms into Urdu.",
    ]
    if is_computer:
        lines.append(
            "SUBJECT IS COMPUTER SCIENCE: Punjab Board Computer books use English for technical content. "
            "Write ALL questions in English using the book's exact terms. Do NOT use Urdu translation."
        )
    elif lang == "english":
        lines.append("Write all questions in clear English matching the source material.")
    else:
        lines.append(
            "Match the language of the source excerpts exactly — do not switch scripts or translate."
        )
    return " ".join(lines)


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


def generate_questions_batched(
    chapter_title,
    content_text,
    mcq_count=0,
    short_count=0,
    long_count=0,
    page_count=None,
    subject_name="",
):
    """
    Large Punjab papers (e.g. 17 MCQ + 33 short + 5 long) need several Gemini calls.
    Small papers still use a single call.
    """
    mcq_count = int(mcq_count or 0)
    short_count = int(short_count or 0)
    long_count = int(long_count or 0)
    total = mcq_count + short_count + long_count
    if total < 1:
        raise ValueError("Select at least one question type with count > 0.")
    # Weekly / monthly papers fit in one Gemini call (saves free-tier quota).
    if total <= 25:
        return generate_questions_from_content(
            chapter_title,
            content_text,
            mcq_count=mcq_count,
            short_count=short_count,
            long_count=long_count,
            page_count=page_count,
            subject_name=subject_name,
        )

    pause = float(os.getenv("QUESTION_GEN_BATCH_PAUSE", "3"))
    mcq_chunk = int(os.getenv("QUESTION_GEN_MCQ_CHUNK", "20"))
    short_chunk = int(os.getenv("QUESTION_GEN_SHORT_CHUNK", "20"))
    long_chunk = int(os.getenv("QUESTION_GEN_LONG_CHUNK", "5"))

    all_items = []
    last_info = {}
    remaining = {"mcq": mcq_count, "short": short_count, "long": long_count}

    def pull(mcq, short, long):
        nonlocal last_info, all_items
        items, info = generate_questions_from_content(
            chapter_title,
            content_text,
            mcq_count=mcq,
            short_count=short,
            long_count=long,
            page_count=page_count,
            subject_name=subject_name,
        )
        if info.get("demoFallback"):
            full_items, full_info = fallback_questions_from_content(
                chapter_title,
                content_text,
                mcq_count=mcq_count,
                short_count=short_count,
                long_count=long_count,
            )
            all_items = full_items
            last_info = full_info
            remaining["mcq"] = remaining["short"] = remaining["long"] = 0
            return
        all_items.extend(items)
        last_info = info
    chunks = [
        ("mcq", mcq_chunk),
        ("short", short_chunk),
        ("long", long_chunk),
    ]
    first = True
    for qtype, size in chunks:
        while remaining[qtype] > 0:
            n = min(remaining[qtype], size)
            if not first and pause > 0:
                time.sleep(pause)
            first = False
            pull(
                n if qtype == "mcq" else 0,
                n if qtype == "short" else 0,
                n if qtype == "long" else 0,
            )
            remaining[qtype] -= n

    return all_items, last_info


def generate_questions_from_content(
    chapter_title,
    content_text,
    mcq_count=3,
    short_count=2,
    long_count=1,
    page_count=None,
    subject_name="",
):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY missing in backend/.env")

    from .content_clean import require_usable_text

    content = require_usable_text(content_text or "", chapter_title)
    if len(content) < 30:
        raise ValueError("Chapter content is too short. Paste at least a paragraph.")

    content_slice, total_chars, used_chars, truncated, coverage = _content_for_questions(content)
    content_lang = _detect_content_language(content)
    if "computer" in (subject_name or "").lower():
        content_lang = "english"
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

    prompt = f"""You are preparing an official Punjab Board examination paper from the textbook chapter below.
Return JSON only. Follow Punjab Board paper format — not conversational AI style.

LANGUAGE AND WORDING (mandatory):
{_language_instruction(content_lang, subject_name)}

SUBJECT: {subject_name or "Punjab Board"}
CHAPTER: {chapter_title}

PUNJAB BOARD FORMAT RULES:
- Section A (Objective): MCQs numbered 1, 2, 3… Each has 4 options (one correct). Options are answer text only.
- Section B (Short Questions): Brief questions suitable for 2 marks each. Use board-style phrasing (Define, Explain, Write, State).
- Section C (Long Questions): Detailed questions. Use parts (a) and (b) with mark hints where appropriate.
- Every question must reference a specific topic, definition, formula, or exercise from the chapter text.
- Use headings and numbering as in Punjab Board papers. Professional formal tone.
- NEVER use placeholder text like "Concept from chapter", "Explain a topic", or "Discuss in detail".
- Do NOT invent new wording — base questions on the textbook content and end-of-chapter exercises.
- Batch {batch_id}: cover early, middle, and late sections. Focus: {", ".join(focus_pick)}.

{{
  "questions": [
    {{
      "questionType": "mcq",
      "questionText": "Board-style MCQ from a named topic in {chapter_title}?",
      "options": ["option one", "option two", "option three", "option four"],
      "correctAnswer": "B",
      "difficulty": "easy|medium|hard"
    }},
    {{
      "questionType": "short",
      "questionText": "Define ... / Explain ... / State ... (from a named topic)",
      "options": [],
      "correctAnswer": "model answer from textbook",
      "difficulty": "medium"
    }},
    {{
      "questionType": "long",
      "questionText": "(a) First part from topic X. (4)\\n(b) Second part from topic Y. (4)",
      "options": [],
      "correctAnswer": "outline from textbook",
      "difficulty": "hard"
    }}
  ]
}}

Counts: exactly {mcq_count} mcq, {short_count} short, {long_count} long.

MCQ rules: options are answer text only (no A/B/C prefix). correctAnswer = single letter A-D.

Content:
{content_slice}
"""

    try:
        data = _call_gemini_json(prompt, api_key, temperature=0.35)
    except (RuntimeError, requests.RequestException) as exc:
        if _demo_fallback_for_error(exc):
            return fallback_questions_from_content(
                chapter_title,
                content,
                mcq_count=mcq_count,
                short_count=short_count,
                long_count=long_count,
            )
        raise

    questions = data.get("questions") or []
    if not questions:
        if demo_fallback_enabled():
            return fallback_questions_from_content(
                chapter_title,
                content,
                mcq_count=mcq_count,
                short_count=short_count,
                long_count=long_count,
            )
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
        "demoFallback": False,
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
