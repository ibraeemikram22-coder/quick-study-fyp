import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

ALLOWED_BULLETS = (3, 5, 7, 10, 15)
FAST_MAX_CHARS = 14000  # used only for quick_mode opt-in
CHUNK_CHARS = int(os.getenv("SUMMARIZER_CHUNK_CHARS", "45000"))
MAX_INPUT_CHARS = CHUNK_CHARS
# Process entire file (no 6-part cap)
MAX_CHUNKS_PROCESS = int(os.getenv("SUMMARIZER_MAX_CHUNKS", "80"))
PARALLEL_WORKERS = int(os.getenv("SUMMARIZER_PARALLEL_WORKERS", "4"))
PARALLEL_BATCH_DELAY = float(os.getenv("SUMMARIZER_BATCH_DELAY", "1.5"))
POINTS_PER_CHUNK = 2

from modules.gemini_config import (
    RETRYABLE_STATUSES as RETRYABLE_STATUS,
    SKIP_MODEL_STATUSES,
    gemini_model_chain,
    gemini_url as _gemini_url,
)
MAX_RETRIES_PER_MODEL = 3
RETRY_BACKOFF_SEC = (2, 5, 10)

# Backup order when Gemini is busy (override with GEMINI_SUMMARIZER_MODEL in .env)
SUMMARIZER_MODELS = (
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
)


def _model_chain():
    override = (os.getenv("GEMINI_SUMMARIZER_MODEL") or "").strip()
    if override:
        rest = [m for m in SUMMARIZER_MODELS if m != override]
        return (override,) + tuple(rest)
    return SUMMARIZER_MODELS


def _word_count(text):
    """Works for English and Urdu/Arabic script (not only ASCII words)."""
    t = text or ""
    words = re.findall(r"[\w\u0600-\u06FF\u0750-\u077F]+", t, flags=re.UNICODE)
    if len(words) >= 5:
        return len(words)
    return len(re.findall(r"\S+", t))


def suggest_bullet_count(word_count):
    """Rough guide: longer notes need more bullets to cover main ideas."""
    if word_count < 400:
        return 3
    if word_count < 900:
        return 5
    if word_count < 1800:
        return 7
    if word_count < 3500:
        return 10
    return 15


def _normalize_output_language(value):
    v = (value or "same").strip().lower()
    if v in ("urdu", "ur"):
        return "urdu"
    if v in ("english", "en"):
        return "english"
    return "same"


def _normalize_content_type(value):
    v = (value or "notes").strip().lower()
    if v in ("math", "mathematics", "numerical", "maths"):
        return "math"
    return "notes"


def _language_instruction(output_lang):
    if output_lang == "urdu":
        return (
            "Write ALL output (chapterTitle, section headings, every bullet, and insight lists) "
            "in Urdu script. Use clear, simple Urdu suitable for students."
        )
    if output_lang == "english":
        return (
            "Write ALL output in English only, even when the source text is Urdu or mixed."
        )
    return (
        "Use the SAME language as the input (Urdu source → Urdu output; English source → English output)."
    )


def _math_instruction(content_type):
    if content_type != "math":
        return ""
    return """
- This is MATHEMATICS content. Under each section:
  - For exercises/problems found in the text, add bullets with short step-by-step solutions.
  - Keep equations readable (e.g. x^2, a/b, √n).
  - State the final answer clearly.
  - If data is missing to solve, say what is needed.
- Include key formulas and methods as study bullets.
"""


def _clamp_bullets(bullets):
    try:
        n = int(bullets)
    except (TypeError, ValueError):
        n = 5
    if n not in ALLOWED_BULLETS:
        n = min(ALLOWED_BULLETS, key=lambda x: abs(x - n))
    return n


def _extract_bullets(summary):
    text = (summary or "").strip()
    if not text:
        return []

    if "•" in text:
        parts = re.split(r"\s*•\s*", text)
        items = [p.strip() for p in parts if p.strip()]
        if items:
            return items

    items = []
    for line in re.split(r"\n+", text):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\-\*\u2022\d]+[\.\)]\s*", "", line).strip()
        if line:
            items.append(line)
    return items


def _format_bullets(items, count):
    cleaned = []
    for item in items:
        line = re.sub(r"^[\-\*\u2022]+\s*", "", (item or "").strip())
        if line:
            cleaned.append(line)
    if len(cleaned) > count:
        cleaned = cleaned[:count]
    return "\n".join(f"• {line}" for line in cleaned)


def _parse_gemini_response(data):
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no summary.")

    parts = candidates[0].get("content", {}).get("parts") or []
    text = ""
    for p in parts:
        if isinstance(p, dict) and "text" in p:
            text += p["text"]
        elif isinstance(p, str):
            text += p

    if not text.strip():
        raise RuntimeError("Empty Gemini response.")
    return text.strip()


def _friendly_api_error(status_code, detail):
    detail_lower = (detail or "").lower()
    if status_code in RETRYABLE_STATUS or "unavailable" in detail_lower:
        return (
            "Gemini is busy (high demand). Wait 1–2 minutes and try again. "
            "We retried several models with delays. "
            "If it keeps failing, try again in 5 minutes or use Quick-only mode."
        )
    if status_code == 429:
        return "API rate limit reached. Wait a minute and try again."
    return f"Gemini API error ({status_code}): {detail[:200]}"


def _call_gemini(prompt, api_key, json_mode=True):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}

    last_error = "Unknown error"
    models = _model_chain()

    for model in models:
        url = _gemini_url(model)
        for attempt in range(MAX_RETRIES_PER_MODEL):
            try:
                response = requests.post(
                    url,
                    params={"key": api_key},
                    json=body,
                    timeout=75,
                )
            except requests.RequestException as exc:
                last_error = str(exc)
                if attempt < MAX_RETRIES_PER_MODEL - 1:
                    time.sleep(RETRY_BACKOFF_SEC[attempt])
                    continue
                break

            if response.ok:
                return _parse_gemini_response(response.json())

            status = response.status_code
            detail = response.text[:300]
            last_error = _friendly_api_error(status, detail)

            if status in SKIP_MODEL_STATUSES:
                break

            if status not in RETRYABLE_STATUS:
                raise RuntimeError(last_error)

            if attempt < MAX_RETRIES_PER_MODEL - 1:
                time.sleep(RETRY_BACKOFF_SEC[attempt])
                continue
            break

    raise RuntimeError(last_error)


def _parse_ai_payload(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            return json.loads(match.group())
        raise RuntimeError("Could not parse AI response.")


def _split_at_paragraphs(text, max_len=CHUNK_CHARS):
    """Split long chapter text at paragraph breaks for multiple AI passes."""
    text = (text or "").strip()
    if len(text) <= max_len:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        if end < len(text):
            split_at = text.rfind("\n\n", start, end)
            if split_at <= start + max_len // 3:
                split_at = text.rfind("\n", start, end)
            if split_at > start:
                end = split_at + 1
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


def _normalize_section_list(raw_sections, max_bullets=None):
    sections = []
    total = 0
    for raw in raw_sections or []:
        if isinstance(raw, str):
            heading = "Main points"
            bullets = _extract_bullets(raw)
        elif isinstance(raw, dict):
            heading = (raw.get("heading") or raw.get("title") or "Main points").strip()
            bullets = raw.get("bullets") or raw.get("points") or []
            if isinstance(bullets, str):
                bullets = _extract_bullets(bullets)
            bullets = [str(b).strip() for b in bullets if str(b).strip()]
        else:
            continue

        cleaned = []
        for b in bullets:
            b = re.sub(r"^[\-\*\u2022]+\s*", "", b).strip()
            if b:
                cleaned.append(b)
        if not cleaned:
            continue

        if max_bullets is not None:
            remaining = max_bullets - total
            if remaining <= 0:
                break
            cleaned = cleaned[:remaining]
            total += len(cleaned)

        sections.append({"heading": heading or "Main points", "bullets": cleaned})
    return sections


def _merge_sections(section_groups):
    order = []
    merged = {}
    for group in section_groups:
        for sec in group:
            key = (sec.get("heading") or "Main points").strip().lower()
            if key not in merged:
                merged[key] = {
                    "heading": sec.get("heading") or "Main points",
                    "bullets": [],
                }
                order.append(key)
            for bullet in sec.get("bullets") or []:
                bullet = str(bullet).strip()
                if bullet and bullet not in merged[key]["bullets"]:
                    merged[key]["bullets"].append(bullet)
    return [merged[k] for k in order]


def _sections_to_plain(sections, chapter_title=None):
    lines = []
    if chapter_title:
        lines.append(chapter_title.strip())
        lines.append("")
    for sec in sections:
        lines.append(sec["heading"])
        for b in sec["bullets"]:
            lines.append(f"• {b}")
        lines.append("")
    return "\n".join(lines).strip()


def _structured_prompt(
    chunk,
    bullets,
    part_note="",
    file_name=None,
    output_language="same",
    content_type="notes",
):
    title_hint = (file_name or "Chapter").replace("_", " ")
    lang_rule = _language_instruction(output_language)
    math_rule = _math_instruction(content_type)
    return f"""You are a study-notes summarizer for students. Return JSON only.

{{
  "chapterTitle": "short main title for this content",
  "sections": [
    {{
      "heading": "topic name or heading from the text",
      "bullets": ["one clear study point", "another point"]
    }}
  ],
  "removed_or_redundant": ["filler removed"],
  "simplified_terms": [{{"from": "hard term", "to": "simpler"}}],
  "kept_key_terms": ["key concept"]
}}

Rules:
- Read the full text below. If it has headings (numbered lines, ALL CAPS titles, short title lines, "Chapter", "Topic", etc.), create one section per heading and keep similar heading names.
- If there are no clear headings, group content into 2-5 logical sections with clear heading names.
- Use about {bullets} bullet points in total across all sections.
- {lang_rule}
- Do not invent facts.
{math_rule}
- chapterTitle: one line ({title_hint}).
{part_note}

Text:
{chunk}
"""


def _summarize_structured_chunk(
    chunk,
    bullets,
    api_key,
    part_note="",
    file_name=None,
    output_language="same",
    content_type="notes",
):
    prompt = _structured_prompt(
        chunk, bullets, part_note, file_name, output_language, content_type
    )
    ai = _parse_ai_payload(_call_gemini(prompt, api_key, json_mode=True))
    sections = _normalize_section_list(ai.get("sections"))
    if not sections:
        fallback = (ai.get("summary") or "").strip()
        if fallback:
            sections = _normalize_section_list([{"heading": "Summary", "bullets": _extract_bullets(fallback)}])
    return {
        "chapterTitle": (ai.get("chapterTitle") or "").strip(),
        "sections": sections,
        "insights": {
            "removed": _as_string_list(ai.get("removed_or_redundant")),
            "simplified": _normalize_simplified(ai.get("simplified_terms")),
            "keptImportant": _as_string_list(ai.get("kept_key_terms")),
        },
    }


def _fast_extract_prompt(chunk, part_num, total_parts, output_language):
    return f"""Extract study points from part {part_num} of {total_parts}. JSON only:
{{"topic": "short label for this part", "points": ["point 1", "point 2", "point 3"]}}
Rules:
- Max {POINTS_PER_CHUNK} points.
- {_language_instruction(output_language)}
- Cover main events/ideas in THIS part only.
Text:
{chunk}
"""


def _extract_chunk_points(args):
    idx, chunk, total, api_key, output_language = args
    prompt = _fast_extract_prompt(chunk, idx + 1, total, output_language)
    try:
        ai = _parse_ai_payload(_call_gemini(prompt, api_key))
        points = _as_string_list(ai.get("points"))
        return {
            "part": idx + 1,
            "topic": (ai.get("topic") or f"Part {idx + 1}").strip(),
            "points": points[:POINTS_PER_CHUNK],
        }
    except Exception:
        return {"part": idx + 1, "topic": f"Part {idx + 1}", "points": []}


def _compile_part_notes(part_results):
    lines = []
    for row in sorted(part_results, key=lambda x: x["part"]):
        lines.append(f"=== Part {row['part']}: {row['topic']} ===")
        for p in row.get("points") or []:
            lines.append(f"- {p}")
    return "\n".join(lines)


def _merge_prompt(compiled_notes, bullets, file_name, output_language, content_type):
    title_hint = (file_name or "Document").replace("_", " ")
    math_rule = _math_instruction(content_type)
    math_block = math_rule if math_rule else ""
    return f"""You are creating FINAL study notes for the ENTIRE document below.
The notes were extracted part-by-part; merge them into one clear flow.

Return JSON only:
{{
  "chapterTitle": "title for whole document",
  "sections": [
    {{"heading": "section heading", "bullets": ["point", "..."]}}
  ],
  "removed_or_redundant": ["..."],
  "simplified_terms": [{{"from": "...", "to": "..."}}],
  "kept_key_terms": ["..."]
}}

Rules:
- Cover the FULL story/topics from part 1 through the last part (beginning, middle, end).
- Order sections in reading order (plot / chapter flow).
- Use about {bullets} bullets total across all sections.
- {_language_instruction(output_language)}
- Do not invent facts not present in the notes.
{math_block}
- chapterTitle: {title_hint}

Part-by-part notes:
{compiled_notes[:90000]}
"""


def _parallel_extract_parts(chunks, api_key, output_language, progress_callback=None):
    total = len(chunks)
    tasks = [(i, ch, total, api_key, output_language) for i, ch in enumerate(chunks)]
    results = [None] * total
    done = 0
    workers = max(1, min(PARALLEL_WORKERS, total))
    batch_size = workers

    for batch_start in range(0, total, batch_size):
        batch = tasks[batch_start : batch_start + batch_size]
        with ThreadPoolExecutor(max_workers=min(workers, len(batch))) as pool:
            futures = {pool.submit(_extract_chunk_points, t): t[0] for t in batch}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as exc:
                    raise RuntimeError(
                        f"Failed on part {idx + 1} of {total}: {exc}"
                    ) from exc
                done += 1
                if progress_callback:
                    pct = 10 + int(65 * done / total)
                    progress_callback(
                        pct,
                        f"Reading document: part {done} of {total} analyzed…",
                    )
        if batch_start + batch_size < total and PARALLEL_BATCH_DELAY > 0:
            time.sleep(PARALLEL_BATCH_DELAY)

    return [r for r in results if r]


def _merge_insights(insight_list):
    removed, simplified, kept = [], [], []
    seen_r, seen_k = set(), set()
    for ins in insight_list:
        for item in ins.get("removed") or []:
            if item not in seen_r:
                seen_r.add(item)
                removed.append(item)
        simplified.extend(ins.get("simplified") or [])
        for item in ins.get("keptImportant") or []:
            if item not in seen_k:
                seen_k.add(item)
                kept.append(item)
    return {
        "removed": removed[:12],
        "simplified": simplified[:8],
        "keptImportant": kept[:12],
    }


def _finish_chapter_payload(
    sections,
    chapter_title,
    insights,
    bullets,
    source,
    file_name,
    output_language,
    content_type,
    original_words,
    summary,
    total_chars,
    clipped_len,
    meta_extra,
):
    summary_words = _word_count(summary)
    actual_bullets = sum(len(s["bullets"]) for s in sections)
    reduction = 0
    if original_words > 0:
        reduction = round((1 - summary_words / original_words) * 100)
    meta = {
        "source": source,
        "fileName": file_name,
        "formatStyle": "chapter",
        "originalWords": original_words,
        "summaryWords": summary_words,
        "reductionPercent": max(0, min(reduction, 99)),
        "bulletCount": bullets,
        "actualBulletCount": actual_bullets,
        "bulletCountMatched": actual_bullets <= bullets,
        "characterCount": clipped_len,
        "totalCharacters": total_chars,
        "outputLanguage": output_language,
        "contentType": content_type,
    }
    meta.update(meta_extra)
    return {
        "summary": summary,
        "chapterTitle": chapter_title,
        "sections": sections,
        "meta": meta,
        "insights": insights,
    }


def _trim_sections_to_bullets(sections, bullets):
    flat_count = sum(len(s["bullets"]) for s in sections)
    if flat_count <= bullets:
        return sections
    remaining = bullets
    trimmed = []
    for sec in sections:
        if remaining <= 0:
            break
        take = sec["bullets"][:remaining]
        remaining -= len(take)
        trimmed.append({"heading": sec["heading"], "bullets": take})
    return trimmed


def generate_chapter_summary(
    text,
    bullets,
    source="text",
    file_name=None,
    output_language="same",
    content_type="notes",
    progress_callback=None,
    full_document=True,
    quick_mode=False,
):
    output_language = _normalize_output_language(output_language)
    content_type = _normalize_content_type(content_type)
    quick_mode = bool(quick_mode)
    full_document = True if full_document is None else bool(full_document)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY missing. Add it to backend/.env (same key as humanizer)."
        )

    if _word_count(text) < 20:
        raise ValueError(
            "Text is too short to summarize. Paste at least a short paragraph."
        )

    def _progress(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    total_chars = len(text)
    original_words = _word_count(text)

    # Optional quick mode: first pages only (~10–20 sec)
    if quick_mode and not full_document:
        clipped = text[:FAST_MAX_CHARS]
        partial = total_chars > len(clipped)
        result = _summarize_structured_chunk(
            clipped,
            bullets,
            api_key,
            "",
            file_name,
            output_language,
            content_type,
        )
        sections = _trim_sections_to_bullets(result["sections"], bullets)
        if not sections:
            raise RuntimeError("AI returned no structured summary.")
        summary = _sections_to_plain(sections, result.get("chapterTitle"))
        return _finish_chapter_payload(
            sections,
            result.get("chapterTitle") or "",
            result["insights"],
            bullets,
            source,
            file_name,
            output_language,
            content_type,
            original_words,
            summary,
            total_chars,
            len(clipped),
            {
                "fastMode": True,
                "partialFile": partial,
                "truncated": partial,
                "chunkCount": 1,
                "totalChunksInFile": max(
                    1, (total_chars + CHUNK_CHARS - 1) // CHUNK_CHARS
                ),
                "processedCharacters": len(clipped),
                "suggestedBulletCount": suggest_bullet_count(_word_count(clipped)),
            },
        )

    all_chunks = _split_at_paragraphs(text, CHUNK_CHARS)
    partial_file = len(all_chunks) > MAX_CHUNKS_PROCESS
    chunks = all_chunks[:MAX_CHUNKS_PROCESS] if partial_file else all_chunks
    clipped_len = sum(len(c) for c in chunks)

    _progress(5, f"Reading entire file ({len(chunks)} parts in parallel)…")

    if len(chunks) == 1:
        _progress(20, "Summarizing…")
        result = _summarize_structured_chunk(
            chunks[0],
            bullets,
            api_key,
            "",
            file_name,
            output_language,
            content_type,
        )
        sections = result["sections"]
        chapter_title = result.get("chapterTitle") or ""
        insights = result["insights"]
        _progress(95, "Formatting…")
    else:
        # Long text: parallel read of ALL parts → one merge (full document flow)
        _progress(8, f"Document split into {len(chunks)} parts — analyzing in parallel…")
        part_results = _parallel_extract_parts(
            chunks, api_key, output_language, _progress
        )
        if not part_results:
            raise RuntimeError("Could not analyze document parts.")

        _progress(78, "Building full summary from all parts…")
        compiled = _compile_part_notes(part_results)
        merge_prompt = _merge_prompt(
            compiled, bullets, file_name, output_language, content_type
        )
        ai = _parse_ai_payload(_call_gemini(merge_prompt, api_key, json_mode=True))
        sections = _normalize_section_list(ai.get("sections"), max_bullets=bullets)
        if not sections:
            raise RuntimeError("AI returned no structured summary.")
        chapter_title = (ai.get("chapterTitle") or "").strip()
        insights = {
            "removed": _as_string_list(ai.get("removed_or_redundant")),
            "simplified": _normalize_simplified(ai.get("simplified_terms")),
            "keptImportant": _as_string_list(ai.get("kept_key_terms")),
        }
        _progress(95, "Formatting…")

    sections = _trim_sections_to_bullets(sections, bullets)
    summary = _sections_to_plain(sections, chapter_title)
    _progress(100, "Complete")
    return _finish_chapter_payload(
        sections,
        chapter_title,
        insights,
        bullets,
        source,
        file_name,
        output_language,
        content_type,
        original_words,
        summary,
        total_chars,
        clipped_len,
        {
            "fastMode": False,
            "truncated": len(chunks) > 1,
            "chunkCount": len(chunks),
            "totalChunksInFile": len(all_chunks),
            "partialFile": partial_file,
            "processedCharacters": clipped_len,
            "fullDocument": True,
            "suggestedBulletCount": suggest_bullet_count(original_words),
        },
    )


def generate_summary(
    text,
    bullets=5,
    source="text",
    file_name=None,
    format_style="chapter",
    output_language="same",
    content_type="notes",
    progress_callback=None,
    full_document=True,
    quick_mode=False,
):
    output_language = _normalize_output_language(output_language)
    content_type = _normalize_content_type(content_type)
    full_document = True if full_document is None else bool(full_document)
    quick_mode = bool(quick_mode)

    if isinstance(text, list):
        text = " ".join(text)

    text = str(text).strip()
    if not text:
        raise ValueError("No text provided.")

    bullets = _clamp_bullets(bullets)

    if (format_style or "chapter").lower() != "bullets":
        return generate_chapter_summary(
            text,
            bullets,
            source,
            file_name,
            output_language,
            content_type,
            progress_callback,
            full_document,
            quick_mode,
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY missing. Add it to backend/.env (same key as humanizer)."
        )

    total_chars = len(text)
    clipped = text[:MAX_INPUT_CHARS]
    truncated = total_chars > len(clipped)
    original_words = _word_count(clipped)
    suggested_bullets = suggest_bullet_count(original_words)
    if original_words < 20:
        raise ValueError(
            "Text is too short to summarize. Paste at least a short paragraph."
        )

    prompt = f"""You are a study-notes summarizer for students. Return JSON only.

Required JSON shape:
{{
  "summary": "exactly {bullets} bullet points separated by newline, each line starting with • ",
  "removed_or_redundant": ["short phrases or filler removed from original"],
  "simplified_terms": [{{"from": "complex word/phrase", "to": "simpler version used"}}],
  "kept_key_terms": ["important terms/concepts kept in summary"]
}}

Rules:
- {_language_instruction(output_language)}
- summary: exactly {bullets} bullets; one main idea per bullet; no intro sentence.
- Cover all major sections/themes from the text; do not invent facts.
{_math_instruction(content_type)}
- removed_or_redundant: 3-8 items actually cut or merged (not generic).
- simplified_terms: 2-6 real simplifications, or [] if none.
- kept_key_terms: 3-8 key concepts preserved.

Text:
{clipped}
"""

    raw = _call_gemini(prompt, api_key)
    ai = _parse_ai_payload(raw)

    raw_summary = (ai.get("summary") or "").strip()
    if not raw_summary:
        raise RuntimeError("AI returned empty summary.")

    bullet_items = _extract_bullets(raw_summary)
    summary = _format_bullets(bullet_items, bullets)
    if not summary:
        raise RuntimeError("AI returned empty summary.")

    actual_bullets = len(_extract_bullets(summary))

    summary_words = _word_count(summary)

    reduction = 0
    if original_words > 0:
        reduction = round((1 - summary_words / original_words) * 100)

    return {
        "summary": summary,
        "meta": {
            "source": source,
            "fileName": file_name,
            "formatStyle": "bullets",
            "originalWords": original_words,
            "summaryWords": summary_words,
            "reductionPercent": max(0, min(reduction, 99)),
            "bulletCount": bullets,
            "actualBulletCount": actual_bullets,
            "bulletCountMatched": actual_bullets == bullets,
            "characterCount": len(clipped),
            "totalCharacters": total_chars,
            "truncated": truncated,
            "suggestedBulletCount": suggested_bullets,
            "outputLanguage": output_language,
            "contentType": content_type,
            "fastMode": True,
            "partialFile": truncated,
        },
        "insights": {
            "removed": _as_string_list(ai.get("removed_or_redundant")),
            "simplified": _normalize_simplified(ai.get("simplified_terms")),
            "keptImportant": _as_string_list(ai.get("kept_key_terms")),
        },
    }


def _as_string_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    out = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif item is not None:
            out.append(str(item).strip())
    return out


def _normalize_simplified(value):
    if not value:
        return []
    out = []
    for item in value:
        if isinstance(item, dict):
            from_val = item.get("from") or item.get("original") or ""
            to_val = item.get("to") or item.get("simplified") or ""
            if from_val or to_val:
                out.append({"from": str(from_val), "to": str(to_val)})
        elif isinstance(item, str) and item.strip():
            out.append({"from": item.strip(), "to": ""})
    return out