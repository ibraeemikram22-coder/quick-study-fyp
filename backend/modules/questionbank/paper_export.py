"""Export practice papers to Word (.docx) for student editing."""

import re


def _clean_mcq_option(opt, index: int) -> str:
    s = str(opt or "").strip()
    s = re.sub(r"^\(?[A-Da-d]\)?[.):\-\s]+", "", s)
    s = re.sub(r"^[A-Da-d]\s+", "", s)
    if re.fullmatch(r"[A-Da-d]", s):
        return f"Option {index + 1}"
    return s or f"Option {index + 1}"


def build_paper_docx(paper: dict, meta: dict | None = None) -> bytes:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Inches, Pt
    except ImportError as exc:
        raise RuntimeError("Install python-docx: pip install python-docx") from exc

    from io import BytesIO

    meta = meta or {}
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.6)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    title = meta.get("examTitle") or paper.get("title") or "Practice Paper"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(16)

    simple = meta.get("simpleLayout")
    if not simple:
        sub = doc.add_paragraph()
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub_run = sub.add_run(meta.get("institute") or "Quick Study Builder")
        sub_run.font.size = Pt(11)

        table = doc.add_table(rows=4, cols=4)
        table.style = "Table Grid"
        rows_data = [
            ("Subject", meta.get("subject") or "—", "Date", meta.get("date") or "—"),
            (
                "Student Name",
                meta.get("studentName") or "________________",
                "Roll No",
                meta.get("rollNo") or "________________",
            ),
            (
                "Time Allowed",
                meta.get("duration") or paper.get("duration") or "—",
                "Total Marks",
                str(paper.get("marks") or "—"),
            ),
            ("Class", meta.get("className") or "—", "Section", meta.get("section") or "—"),
        ]
        for row_idx, (l1, v1, l2, v2) in enumerate(rows_data):
            row = table.rows[row_idx]
            row.cells[0].text = l1
            row.cells[1].text = str(v1)
            row.cells[2].text = l2
            row.cells[3].text = str(v2)
            for cell in row.cells:
                for para in cell.paragraphs:
                    for r in para.runs:
                        r.font.size = Pt(10)
    else:
        info = doc.add_paragraph(
            f"Marks: {paper.get('marks') or '—'}  |  Time: {paper.get('duration') or 'as needed'}"
        )
        info.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in info.runs:
            r.font.size = Pt(10)

    doc.add_paragraph()
    if not simple:
        instr = doc.add_paragraph(
            meta.get("instructions")
            or "Read all questions carefully. Answer in the space provided."
        )
        instr.runs[0].font.size = Pt(10)
        instr.runs[0].italic = True

    for sec in paper.get("sections") or []:
        doc.add_paragraph()
        h = doc.add_paragraph(sec.get("title") or "Section")
        h.runs[0].bold = True
        h.runs[0].font.size = Pt(12)

        for q_idx, q in enumerate(sec.get("questions") or [], start=1):
            qtype = (q.get("questionType") or "").lower()
            text = q.get("questionText") or ""
            para = doc.add_paragraph()
            run = para.add_run(f"Q{q_idx}. ")
            run.bold = True
            run.font.size = Pt(11)
            body = para.add_run(text)
            body.font.size = Pt(11)

            questions_only = meta.get("questionsOnly")
            if qtype == "mcq":
                opts = q.get("options") or []
                labels = "ABCD"
                for i, opt in enumerate(opts[:4]):
                    clean = _clean_mcq_option(opt, i)
                    op = doc.add_paragraph(f"   ({labels[i]}) {clean}")
                    op.paragraph_format.left_indent = Inches(0.35)
                    for r in op.runs:
                        r.font.size = Pt(10)
            elif not questions_only:
                if qtype == "short":
                    doc.add_paragraph("Answer: _________________________________________________")
                else:
                    doc.add_paragraph("Answer:")
                    doc.add_paragraph("_" * 70)
                    doc.add_paragraph("_" * 70)

    if meta.get("includeAnswerKey"):
        doc.add_page_break()
        doc.add_paragraph("ANSWER KEY").runs[0].bold = True
        for sec in paper.get("sections") or []:
            sec_title = sec.get("title") or "Section"
            doc.add_paragraph(sec_title).runs[0].bold = True
            for q_idx, q in enumerate(sec.get("questions") or [], start=1):
                ans = q.get("correctAnswer") or "—"
                line = doc.add_paragraph(f"Q{q_idx}: {ans}")
                line.runs[0].font.size = Pt(10)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
