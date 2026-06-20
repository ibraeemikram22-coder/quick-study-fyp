"""OCR for scanned/image PDFs via Gemini (no manual paste needed)."""
import base64
import os
import time

import requests

from modules.gemini_config import (
    RETRYABLE_STATUSES,
    SKIP_MODEL_STATUSES,
    gemini_model_chain,
    gemini_url,
    is_quota_exceeded,
)

INLINE_PDF_MAX_BYTES = 18 * 1024 * 1024
OCR_BATCH_PAGES = int(os.getenv("PDF_OCR_BATCH_PAGES", "6"))
OCR_DPI = int(os.getenv("PDF_OCR_DPI", "140"))
OCR_PAGE_SLEEP = float(os.getenv("PDF_OCR_PAGE_SLEEP", "0.35"))

OCR_PROMPT = (
    "You are an OCR engine for Punjab board textbooks.\n"
    "Extract ALL readable text from these PDF page(s) in reading order.\n"
    "Rules:\n"
    "- Plain text only (no markdown, no summary)\n"
    "- Keep headings, numbered lists, and paragraph breaks\n"
    "- Include English and Urdu text as accurately as possible\n"
    "- Do not add commentary\n"
)


def _call_gemini_parts(parts, api_key, timeout=300):
    body = {"contents": [{"parts": parts}]}
    last_err = "Gemini OCR unavailable"

    for model in gemini_model_chain():
        for attempt, wait in enumerate((0, 2, 5)):
            if wait:
                time.sleep(wait)
            try:
                res = requests.post(
                    gemini_url(model),
                    params={"key": api_key},
                    json=body,
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                last_err = str(exc)
                continue

            if res.ok:
                data = res.json()
                chunks = (
                    (data.get("candidates") or [{}])[0]
                    .get("content", {})
                    .get("parts")
                    or []
                )
                text = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in chunks
                ).strip()
                if text:
                    return text
                last_err = "Empty OCR response"
                continue

            if res.status_code in SKIP_MODEL_STATUSES:
                last_err = res.text[:200]
                break
            if is_quota_exceeded(res.status_code, res.text):
                last_err = res.text[:200]
                continue
            if res.status_code not in RETRYABLE_STATUSES:
                raise RuntimeError(f"Gemini OCR error ({res.status_code}): {res.text[:200]}")
            last_err = res.text[:200]

    raise RuntimeError(
        f"Scanned PDF OCR failed: {last_err}. Check GEMINI_API_KEY in backend/.env or try again later."
    )


def _ocr_pdf_bytes(pdf_bytes, api_key):
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    parts = [
        {"text": OCR_PROMPT},
        {"inline_data": {"mime_type": "application/pdf", "data": b64}},
    ]
    return _call_gemini_parts(parts, api_key, timeout=360)


def _ocr_pdf_by_pages(path, max_pages, max_chars, api_key):
    try:
        import fitz
    except ImportError:
        raise RuntimeError(
            "Scanned PDF support needs pymupdf. Run: pip install pymupdf"
        )

    doc = fitz.open(path)
    try:
        page_count = len(doc)
        limit = page_count if max_pages is None else min(page_count, int(max_pages))
        texts = []
        total = 0

        for batch_start in range(0, limit, OCR_BATCH_PAGES):
            batch_end = min(batch_start + OCR_BATCH_PAGES, limit)
            parts = [
                {
                    "text": (
                        f"{OCR_PROMPT}\n"
                        f"Pages {batch_start + 1} to {batch_end} of {limit}."
                    )
                }
            ]

            for i in range(batch_start, batch_end):
                page = doc[i]
                pix = page.get_pixmap(dpi=OCR_DPI, alpha=False)
                img_b64 = base64.standard_b64encode(pix.tobytes("jpeg")).decode()
                parts.append(
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                )

            chunk = _call_gemini_parts(parts, api_key, timeout=420)
            texts.append(chunk)
            total += len(chunk)
            if max_chars and total >= max_chars:
                break
            if batch_end < limit:
                time.sleep(OCR_PAGE_SLEEP)

        joined = "\n\n".join(texts).strip()
        if max_chars and len(joined) > max_chars:
            return joined[:max_chars]
        return joined
    finally:
        doc.close()


def ocr_pdf_file(path, max_pages=500, max_chars=2_000_000):
    """Extract text from scanned PDF using Gemini OCR."""
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "Set GEMINI_API_KEY in backend/.env for scanned PDFs, then upload the file again."
        )

    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        pdf_bytes = handle.read()

    if size <= INLINE_PDF_MAX_BYTES:
        text = _ocr_pdf_bytes(pdf_bytes, api_key)
    else:
        text = _ocr_pdf_by_pages(path, max_pages, max_chars, api_key)

    text = (text or "").strip()
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
    return text
