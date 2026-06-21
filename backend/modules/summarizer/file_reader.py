def read_pdf(file):
    return read_pdf_with_meta(file)["text"]


def _read_pdf_pypdf2(file, max_pages=None, max_chars=800_000):
    PdfReader = None
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise RuntimeError(
                "PDF support missing. Run: pip install pypdf python-docx"
            )

    if hasattr(file, "seek"):
        file.seek(0)
    reader = PdfReader(file)
    page_count = len(reader.pages)
    limit = page_count if max_pages is None else min(page_count, int(max_pages))
    parts = []
    total = 0
    truncated_pages = limit < page_count

    for i in range(limit):
        chunk = reader.pages[i].extract_text() or ""
        if not chunk:
            continue
        if max_chars and total + len(chunk) > max_chars:
            parts.append(chunk[: max_chars - total])
            total = max_chars
            truncated_pages = True
            break
        parts.append(chunk)
        total += len(chunk)

    text = "".join(parts).strip()
    return {
        "text": text,
        "pageCount": page_count,
        "pagesRead": limit,
        "charCount": len(text),
        "truncated": truncated_pages or (max_chars and len(text) >= max_chars),
        "method": "pypdf2",
    }


def _read_pdf_pymupdf(file, max_pages=None, max_chars=800_000):
    try:
        import fitz
    except ImportError:
        return None

    if hasattr(file, "seek"):
        file.seek(0)
    raw = file.read() if hasattr(file, "read") else None
    doc = fitz.open(stream=raw, filetype="pdf") if raw is not None else fitz.open(file)
    try:
        page_count = len(doc)
        limit = page_count if max_pages is None else min(page_count, int(max_pages))
        parts = []
        total = 0
        truncated_pages = limit < page_count

        for i in range(limit):
            chunk = doc[i].get_text("text") or ""
            if not chunk.strip():
                continue
            if max_chars and total + len(chunk) > max_chars:
                parts.append(chunk[: max_chars - total])
                total = max_chars
                truncated_pages = True
                break
            parts.append(chunk)
            total += len(chunk)

        text = "\n".join(parts).strip()
        return {
            "text": text,
            "pageCount": page_count,
            "pagesRead": limit,
            "charCount": len(text),
            "truncated": truncated_pages or (max_chars and len(text) >= max_chars),
            "method": "pymupdf",
        }
    finally:
        doc.close()


def read_pdf_with_meta(file, max_pages=None, max_chars=800_000):
    meta = _read_pdf_pypdf2(file, max_pages=max_pages, max_chars=max_chars)
    if meta["charCount"] >= 30:
        return meta

    alt = _read_pdf_pymupdf(file, max_pages=max_pages, max_chars=max_chars)
    if alt and alt["charCount"] > meta["charCount"]:
        return alt
    return meta


def read_pdf_from_path(path, max_pages=None, max_chars=800_000, ocr_fallback=True):
    """
    Read PDF from disk. If text layer is empty (scanned PDF), run Gemini OCR automatically.
    """
    with open(path, "rb") as handle:
        meta = read_pdf_with_meta(handle, max_pages=max_pages, max_chars=max_chars)

    if meta["charCount"] >= 30 or not ocr_fallback:
        return meta

    from modules.summarizer.pdf_ocr import ocr_pdf_file

    ocr_text = ocr_pdf_file(path, max_pages=max_pages, max_chars=max_chars)
    if len(ocr_text) < 30:
        raise RuntimeError(
            "Could not extract text from this PDF (low-quality scan). "
            "Try another file or a smaller compressed PDF."
        )

    page_count = meta.get("pageCount") or 0
    pages_read = meta.get("pagesRead") or page_count
    truncated = bool(meta.get("truncated"))
    if max_pages and page_count > max_pages:
        truncated = True
        pages_read = min(page_count, int(max_pages))

    return {
        "text": ocr_text,
        "pageCount": page_count,
        "pagesRead": pages_read,
        "charCount": len(ocr_text),
        "truncated": truncated or (max_chars and len(ocr_text) >= max_chars),
        "method": "gemini_ocr",
        "ocrUsed": True,
    }


def read_docx(file):
    try:
        import docx
    except ImportError:
        raise RuntimeError(
            "DOCX support missing. Run: pip install python-docx"
        )

    doc = docx.Document(file)
    lines = []
    for para in doc.paragraphs:
        t = (para.text or "").strip()
        if not t:
            continue
        style = getattr(para.style, "name", "") or ""
        if "Heading" in style:
            lines.append(f"\n## {t}\n")
        else:
            lines.append(t)
    return "\n".join(lines)


def read_txt(file):
    raw = file.read()
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore")
    return raw
