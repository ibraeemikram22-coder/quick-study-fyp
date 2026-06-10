import json
import os
import random
import re
import time

import requests

from modules.gemini_config import (
    RETRYABLE_STATUSES,
    SKIP_MODEL_STATUSES,
    gemini_model_chain,
    gemini_url,
)

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "into", "such",
    "like", "while", "when", "where", "which", "their", "they", "them",
    "have", "has", "been", "being", "were", "was", "are", "is",
    "can", "may", "will", "also", "often", "called", "because", "allow",
    "users", "enter", "display", "include", "includes", "other", "main",
    "system", "systems", "useful", "information", "data", "results",
    "perform", "performs", "controls", "convert", "converts", "processes",
    "electronic", "device", "devices", "allow", "allows",
    "calculations", "processing", "components", "displays", "display",
    "enters", "enter", "computer", "passage", "material", "used", "using",
}


def _call_gemini(prompt, api_key):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
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
                    timeout=90,
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


def _parse_json_block(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _norm_opt(s):
    return re.sub(r"\s+", " ", str(s or "").strip())


def _dedupe_options(options):
    seen = set()
    out = []
    for o in options:
        key = _norm_opt(o).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(_norm_opt(o))
    return out


def _validate_question(q):
    question = _norm_opt(q.get("question"))
    options = _dedupe_options(q.get("options") or [])
    answer = _norm_opt(q.get("answer"))

    if not question or len(options) < 3 or not answer:
        return None
    if answer.lower() in STOPWORDS or len(answer) < 2:
        return None

    # Answer must be one of the options (case-insensitive match, keep canonical answer text)
    matched = None
    for o in options:
        if o.lower() == answer.lower():
            matched = o
            break
    if not matched:
        options = options[:3] + [answer]
    else:
        answer = matched

    options = _dedupe_options(options)
    if len(options) < 4:
        return None
    options = options[:4]

    # Reject if options look unrelated (one very long, others very short)
    lengths = [len(o) for o in options]
    if max(lengths) > 3 * max(min(lengths), 1):
        return None

    random.shuffle(options)
    return {"question": question, "options": options, "answer": answer}


def generate_with_gemini(text, limit):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    snippet = text[:12000]
    prompt = f"""You are an expert teacher. Create exactly {limit} multiple-choice questions from the passage.

CRITICAL — question and answer must belong TOGETHER:
1. Each question tests ONE fact from ONE sentence (or two neighbouring sentences) only.
2. The correct answer must come directly from that same sentence/context — not from a distant part of the passage.
3. All 4 options must be the SAME TYPE: all device names, OR all definitions, OR all functions — never mix unrelated categories.
4. Wrong options (distractors) must be other real terms from the SAME paragraph/topic — plausible but wrong for THIS question.
5. Keep questions short (under 20 words). Keep options short (1–6 words each).
6. Prefer: "What is X?" / "Which component…?" / "Fill in: The _____ stores data." (blank = one key term from that sentence)
7. "answer" must exactly match one string in "options".
8. Same language as the source text.

BAD (too disconnected): question about CPU with answer "keyboard" from another page.
GOOD: question about CPU with options: CPU, RAM, Monitor, Printer (all computer parts).

Return ONLY valid JSON:
{{"questions":[{{"question":"...","options":["a","b","c","d"],"answer":"b"}}]}}

PASSAGE:
{snippet}
"""

    raw = _call_gemini(prompt, api_key)
    data = _parse_json_block(raw)
    out = []
    for item in data.get("questions") or []:
        valid = _validate_question(item)
        if valid:
            out.append(valid)
        if len(out) >= limit:
            break
    return out if out else None


def _clean_word(word):
    return re.sub(r"[^\w\-]", "", word)


def _extract_key_terms(text):
    terms = []
    seen = set()

    for m in re.finditer(r"\b[A-Z]{2,}\b", text):
        t = m.group(0)
        if t.lower() not in STOPWORDS and t not in seen:
            seen.add(t)
            terms.append(t)

    for m in re.finditer(r"\b[A-Za-z][A-Za-z\-]{3,}\b", text):
        w = _clean_word(m.group(0))
        low = w.lower()
        if low in STOPWORDS or w in seen:
            continue
        if w[0].isupper() or len(w) >= 5:
            seen.add(w)
            terms.append(w)

    return terms


def _terms_in_sentence(sentence, key_terms):
    low_sent = sentence.lower()
    found = []
    for t in key_terms:
        if re.search(r"\b" + re.escape(t) + r"\b", sentence, re.I):
            found.append(t)
    if len(found) >= 4:
        return found
    # Also terms that share first letter / topic — same sentence words
    for t in key_terms:
        if t not in found and t.lower() in low_sent:
            found.append(t)
    return found


def _pick_term_from_sentence(sentence, key_terms):
    in_sent = _terms_in_sentence(sentence, key_terms)
    if in_sent:
        in_sent.sort(key=len, reverse=True)
        return in_sent[0]

    words = [_clean_word(w) for w in sentence.split()]
    words = [w for w in words if w]
    candidates = []
    for w in words:
        if w in key_terms:
            candidates.append(w)
        elif w.lower() not in STOPWORDS and len(w) >= 5 and w[0].isupper():
            candidates.append(w)
    if not candidates:
        return None
    candidates.sort(key=len, reverse=True)
    return candidates[0]


def _make_blank_question(sentence, answer):
    pattern = re.compile(r"\b" + re.escape(answer) + r"\b", re.I)
    if not pattern.search(sentence):
        return None
    blanked = pattern.sub("_____", sentence, count=1)
    # Trim long sentences so question and options feel close
    if len(blanked) > 160:
        blanked = blanked[:157] + "…"
    return blanked


def _make_direct_question(sentence, answer):
    short = sentence.strip()
    if len(short) > 120:
        short = short[:117] + "…"
    return f'According to the text: "{short}" — what is "{answer}"?'


def generate_with_heuristic(text, limit):
    sentences = [
        s.strip()
        for s in re.split(r"[.!?؟۔]\s*", text)
        if len(s.split()) >= 6
    ]
    key_terms = _extract_key_terms(text)
    if len(key_terms) < 4:
        return []

    random.shuffle(sentences)
    questions = []

    for sentence in sentences:
        answer = _pick_term_from_sentence(sentence, key_terms)
        if not answer or answer.lower() in STOPWORDS:
            continue

        # Distractors from SAME sentence first — keeps Q&A context tight
        pool = _terms_in_sentence(sentence, key_terms)
        pool = [t for t in pool if t.lower() != answer.lower()]
        if len(pool) < 3:
            pool = [t for t in key_terms if t.lower() != answer.lower()]

        if len(pool) < 3:
            continue

        wrong = random.sample(pool, 3)
        options = _dedupe_options(wrong + [answer])
        if len(options) < 4:
            continue

        question = _make_blank_question(sentence, answer)
        if not question:
            question = _make_direct_question(sentence, answer)

        random.shuffle(options)
        questions.append(
            {"question": question, "options": options[:4], "answer": answer}
        )
        if len(questions) >= limit:
            break

    return questions


def generate_quiz_questions(text, limit=5):
    limit = max(1, min(int(limit), 15))
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) < 80:
        return []

    try:
        gemini_q = generate_with_gemini(text, limit)
        if gemini_q:
            return gemini_q
    except (json.JSONDecodeError, RuntimeError, KeyError, ValueError):
        pass

    return generate_with_heuristic(text, limit)
