"""Split full book text into named chapters for teacher syllabus selection."""
import json
import os
import re

CHAPTER_LINE = re.compile(
    r"(?im)^\s*"
    r"(?:"
    r"(?:chapter|ch\.?|unit|lesson)\s*[\.\-–:#]?\s*0*(\d{1,2})\s*[\-–:\.]?\s*(.*?)"
    r"|"
    r"(?:CHAPTER|Chapter|UNIT|Unit)\s+0*(\d{1,2})\s*[\-–:\.]?\s*(.*?)"
    r")\s*$"
)

DOT_TITLE = re.compile(
    r"(?m)^\s*0*(\d{1,2})\.\s+([A-Z][A-Za-z0-9\s\-–,'()]{3,80})\s*$"
)

TWO_LINE_HEADER = re.compile(
    r"(?im)^\s*(?:CHAPTER|Chapter|UNIT|Unit)\s+0*(\d{1,2})\s*\r?\n\s*([A-Z][A-Za-z0-9\s\-–,'()]{3,80})\s*$"
)

TOC_LINE = re.compile(
    r"(?im)^\s*(?:chapter|ch\.?|unit)\s*0*(\d{1,2})\s*[\.\-–:]\s*(.+?)\s*\.{2,}\s*\d+\s*$"
)

# Punjab textbook typical chapter counts (class 11 / 12)
EXPECTED_CHAPTERS = {
    "physics 11": 11,
    "physics 12": 11,
    "chemistry 11": 11,
    "chemistry 12": 16,
    "biology 11": 14,
    "biology 12": 15,
    "computer 11": 10,
    "computer 12": 14,
}


def infer_expected_chapters(book_name, class_level=None):
    key = (book_name or "").strip().lower()
    if key in EXPECTED_CHAPTERS:
        return EXPECTED_CHAPTERS[key]
    for pattern, count in EXPECTED_CHAPTERS.items():
        if pattern in key or key in pattern:
            return count
    if class_level in (11, 12):
        return 11
    return None


def _chapter_title(num, name):
    num = int(num)
    name = (name or "").strip(" -–:.")
    if name:
        return f"Chapter {num} — {name[:120]}"
    return f"Chapter {num}"


def _build_chapters_from_matches(content, unique, min_chars):
    chapters = []
    for i, (pos, num, name) in enumerate(unique):
        end = unique[i + 1][0] if i + 1 < len(unique) else len(content)
        chunk = content[pos:end].strip()
        if len(chunk) < min_chars:
            continue
        chapters.append(
            {
                "title": _chapter_title(num, name),
                "content": chunk,
                "sortOrder": num,
            }
        )
    return chapters


def _split_proportional(content, chapter_meta, min_chars=80):
    """Split full book text evenly when headings cannot be found reliably."""
    ordered = sorted(chapter_meta, key=lambda x: int(x.get("num") or x.get("number") or 0))
    n = len(ordered)
    if n < 1:
        return []
    total = len(content)
    chapters = []
    for i, ch in enumerate(ordered):
        num = int(ch.get("num") or ch.get("number") or (i + 1))
        title = (ch.get("title") or ch.get("name") or "").strip()
        start = (total * i) // n
        end = total if i == n - 1 else (total * (i + 1)) // n
        chunk = content[start:end].strip()
        if len(chunk) < min_chars and chapters:
            chapters[-1]["content"] += "\n\n" + chunk
            continue
        chapters.append(
            {
                "title": _chapter_title(num, title),
                "content": chunk,
                "sortOrder": num,
            }
        )
    return chapters if len(chapters) >= 2 else []


def _collect_regex_matches(content):
    matches = []
    for m in CHAPTER_LINE.finditer(content):
        num = m.group(1) or m.group(3)
        name = m.group(2) or m.group(4) or ""
        if num:
            matches.append((m.start(), int(num), name.strip()))

    if len(matches) < 2:
        for m in DOT_TITLE.finditer(content):
            num = int(m.group(1))
            if 1 <= num <= 30:
                matches.append((m.start(), num, m.group(2).strip()))

    if len(matches) < 2:
        for m in TWO_LINE_HEADER.finditer(content):
            matches.append((m.start(), int(m.group(1)), m.group(2).strip()))

    if len(matches) < 2:
        for m in TOC_LINE.finditer(content):
            num = int(m.group(1))
            title = m.group(2).strip()
            pos = _find_chapter_body_start(content, num, title)
            if pos >= 0:
                matches.append((pos, num, title))

    seen = set()
    unique = []
    for pos, num, name in sorted(matches, key=lambda x: x[0]):
        if num in seen:
            continue
        seen.add(num)
        unique.append((pos, num, name))
    return unique


def _find_chapter_body_start(content, num, title):
    title_bit = re.escape((title or "")[:24])
    patterns = [
        rf"(?im)^\s*(?:chapter|ch\.?|unit)\s*0*{num}\s*[\-–:\.]?\s*{title_bit}",
        rf"(?im)^\s*(?:CHAPTER|Chapter|UNIT|Unit)\s+0*{num}\b",
        rf"(?m)^\s*0*{num}\.\s+{title_bit}",
        rf"(?im)\bunit\s+0*{num}\b",
    ]
    for pat in patterns:
        m = re.search(pat, content)
        if m:
            return m.start()
    return -1


def _ai_chapter_list(content, expected_count=None, book_name=None):
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key or len(content) < 2000:
        return []

    try:
        import requests
        from modules.gemini_config import gemini_model_chain, gemini_url
    except ImportError:
        return []

    count_hint = ""
    if expected_count:
        count_hint = f"This book has exactly {expected_count} chapters. List all {expected_count}."
    elif book_name:
        count_hint = f"Book: {book_name}. List every chapter in order."

    head = content[:35000]
    mid = ""
    if len(content) > 120000:
        mid_start = len(content) // 2 - 8000
        mid = content[mid_start : mid_start + 16000]
    tail = content[-20000:] if len(content) > 50000 else ""
    sample = head
    if mid:
        sample += "\n\n[--- middle of book ---]\n\n" + mid
    if tail:
        sample += "\n\n[--- end of book ---]\n\n" + tail

    prompt = f"""Punjab Board textbook. {count_hint}
Return JSON only:
{{"chapters": [{{"num": 1, "title": "Measurement"}}, {{"num": 2, "title": "..."}}, ...]}}

Rules:
- List ALL syllabus chapters in order (do not skip any).
- Use English titles from the book table of contents.
- num must be 1, 2, 3... consecutive.

Text sample:
{sample[:55000]}
"""

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }

    for model in gemini_model_chain():
        try:
            res = requests.post(
                gemini_url(model),
                params={"key": api_key},
                json=body,
                timeout=120,
            )
            if res.ok:
                parts = (res.json().get("candidates") or [{}])[0].get("content", {}).get("parts") or []
                raw = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
                data = json.loads(raw)
                meta = data.get("chapters") or []
                out = []
                for ch in meta:
                    try:
                        num = int(ch.get("num") or ch.get("number") or 0)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= num <= 40:
                        out.append(
                            {
                                "num": num,
                                "title": (ch.get("title") or ch.get("name") or "").strip(),
                            }
                        )
                if out:
                    return sorted(out, key=lambda x: x["num"])
        except Exception:
            continue
    return []


def _split_by_ai(content, min_chars=80, expected_count=None, book_name=None):
    meta = _ai_chapter_list(content, expected_count, book_name)
    if expected_count and len(meta) < expected_count:
        # Pad missing chapter numbers with generic titles
        have = {c["num"] for c in meta}
        for n in range(1, expected_count + 1):
            if n not in have:
                meta.append({"num": n, "title": f"Unit {n}"})
        meta = sorted(meta, key=lambda x: x["num"])[:expected_count]

    if len(meta) < 2:
        return []

    positioned = []
    for ch in meta:
        num = ch["num"]
        title = ch["title"]
        pos = _find_chapter_body_start(content, num, title)
        positioned.append((pos, num, title))

    found = [p for p in positioned if p[0] >= 0]
    if len(found) >= max(2, len(meta) // 2):
        seen = set()
        unique = []
        for pos, num, name in sorted(positioned, key=lambda x: x[0] if x[0] >= 0 else 10**9):
            if num in seen:
                continue
            seen.add(num)
            if pos >= 0:
                unique.append((pos, num, name))
        unique.sort(key=lambda x: x[0])
        chapters = _build_chapters_from_matches(content, unique, min_chars)
        if len(chapters) >= len(meta) * 0.6:
            return chapters

    return _split_proportional(content, meta, min_chars)


def split_text_into_chapters(text, min_chars=80, book_name=None, class_level=None):
    """Return list of {title, content, sortOrder} from book text."""
    content = (text or "").strip()
    if len(content) < min_chars * 2:
        return []

    expected = infer_expected_chapters(book_name, class_level)

    chapters = _split_by_ai(content, min_chars, expected, book_name)
    if expected and len(chapters) >= expected * 0.8:
        return chapters[:expected] if len(chapters) > expected else chapters
    if len(chapters) >= 2:
        return chapters

    unique = _collect_regex_matches(content)
    if len(unique) >= 2:
        chapters = _build_chapters_from_matches(content, unique, min_chars)
        if len(chapters) >= 2:
            return chapters

    if expected:
        meta = [{"num": i, "title": f"Chapter {i}"} for i in range(1, expected + 1)]
        return _split_proportional(content, meta, min_chars)

    return []
