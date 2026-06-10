def read_pdf(file):
    return read_pdf_with_meta(file)["text"]


def read_pdf_with_meta(file):
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise RuntimeError(
            "PDF support missing. Run: pip install PyPDF2 python-docx"
        )

    reader = PdfReader(file)
    page_count = len(reader.pages)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    text = text.strip()
    return {
        "text": text,
        "pageCount": page_count,
        "charCount": len(text),
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
