"""Punjab Board examination section instructions (printed vs attempt)."""

from .subject_patterns import PRE_BOARD_LAYOUT, subject_group

FULL_BOOK_TITLE = "Full Book"

ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]


def board_short_blocks(short_count, short_attempt, marks_each=2):
    """Split shorts into Q.No.2 / Q.No.3 / Q.No.4 (board preboard style)."""
    short_count = int(short_count or 0)
    short_attempt = int(short_attempt or short_count)
    if short_count < 1:
        return []
    if short_count < 9:
        att = min(short_attempt, short_count)
        return [
            {
                "questionNo": 2,
                "boardHead": f"Q.No.2: Write Short Answers to any {att} questions.",
                "marksLine": f"({marks_each}×{att}={marks_each * att})",
                "printed": short_count,
                "attempt": att,
            }
        ]
    base, rem = divmod(short_count, 3)
    sizes = [base + (1 if i < rem else 0) for i in range(3)]
    attempt_each = short_attempt // 3 if short_attempt > 6 else min(6, short_attempt)
    blocks = []
    qno = 2
    for size in sizes:
        if size < 1:
            continue
        att = min(attempt_each, size)
        blocks.append(
            {
                "questionNo": qno,
                "boardHead": f"Q.No.{qno}: Write Short Answers to any {att} questions.",
                "marksLine": f"({marks_each}×{att}={marks_each * att})",
                "printed": size,
                "attempt": att,
            }
        )
        qno += 1
    return blocks


def section_meta_for_exam(exam_code, pattern_row=None, subject_name=None):
    """Return section instructions for paper layout."""
    mcq = int(getattr(pattern_row, "mcq_count", None) or 6)
    short = int(getattr(pattern_row, "short_count", None) or 12)
    long = int(getattr(pattern_row, "long_count", None) or 1)
    s_att = getattr(pattern_row, "short_attempt", None) if pattern_row else None
    l_att = getattr(pattern_row, "long_attempt", None) if pattern_row else None
    short_attempt = int(s_att) if s_att else short
    long_attempt = int(l_att) if l_att else long

    code = (exam_code or "").lower()
    group = subject_group(subject_name) if subject_name else None

    if code == "pre_board" and group in PRE_BOARD_LAYOUT:
        layout = PRE_BOARD_LAYOUT[group]
        mcq = layout["mcq"]
        short = layout["short_count"]
        long = layout["long_count"]
        short_attempt = layout["short_attempt"]
        long_attempt = layout["long_attempt"]
        short_blocks = []
        for blk in layout["short_blocks"]:
            att = blk["attempt"]
            printed = blk["printed"]
            each = blk["marks_each"]
            short_blocks.append(
                {
                    "questionNo": blk["questionNo"],
                    "title": f"Question No. {blk['questionNo']}",
                    "boardHead": (
                        f"Q.No.{blk['questionNo']}: Write Short Answers to any "
                        f"{att} questions."
                    ),
                    "instruction": f"Write short answers to any {att} of the following {printed} questions.",
                    "marksLine": f"({each}×{att}={att * each})",
                    "printed": printed,
                    "attempt": att,
                }
            )
        long_each = layout["long_marks_each"]
        return {
            "objective": {
                "title": "OBJECTIVE (MCQs)",
                "boardHead": "Q.No.1: Encircle the Correct Option.",
                "instruction": f"Choose the correct answer. All {mcq} questions are compulsory.",
                "marksLine": f"(1×{mcq}={mcq})",
            },
            "short": {
                "title": "SECTION — I (Short Questions)",
                "instruction": "Section-I is compulsory.",
                "marksLine": f"Total short section marks: {short_attempt * 2}",
                "blocks": short_blocks,
            },
            "long": {
                "title": "SECTION — II (Long Questions)",
                "boardHead": "SECTION — II (Long Questions)",
                "instruction": f"Attempt any {long_attempt} questions from the following.",
                "marksLine": f"({long_each}×{long_attempt}={long_attempt * long_each})",
                "hasParts": layout["long_has_parts"],
                "longStartNo": 2 + len(layout["short_blocks"]),
            },
            "paperNote": "Section-I is compulsory. Attempt any THREE (3) questions from Section-II.",
        }

    if code in ("pre_board", "half_book"):
        short_blocks = board_short_blocks(short, short_attempt, marks_each=2)
        long_each = 8 if code == "pre_board" else max(8, 12)
        return {
            "objective": {
                "title": "SECTION A — OBJECTIVE (MCQs)",
                "boardHead": "Q.No.1: Encircle the Correct Option.",
                "instruction": f"Choose the correct answer. All {mcq} questions are compulsory.",
                "marksLine": f"(1×{mcq}={mcq})",
            },
            "short": {
                "title": "SECTION B — SHORT QUESTIONS",
                "instruction": f"Attempt ANY {short_attempt} of the following {short} questions.",
                "marksLine": f"{short_attempt} × 2 = {short_attempt * 2}",
                "blocks": short_blocks,
            },
            "long": {
                "title": "SECTION C — LONG QUESTIONS",
                "boardHead": "SECTION — II (Long Questions)",
                "instruction": (
                    f"Attempt ANY {long_attempt} questions. Each question has parts (a) and (b)."
                ),
                "marksLine": f"({long_each}×{long_attempt}={long_each * long_attempt})",
                "longStartNo": 2 + len(short_blocks),
            },
        }

    return {
        "objective": {
            "title": "SECTION A — MCQs",
            "instruction": "Choose the correct answer.",
            "marksLine": f"{mcq} × 1 = {mcq}",
        },
        "short": {
            "title": "SECTION B — SHORT QUESTIONS",
            "instruction": f"Attempt all {short} short questions."
            if short_attempt >= short
            else f"Attempt ANY {short_attempt} of {short} questions.",
            "marksLine": f"{short} × 1 = {short}",
        },
        "long": {
            "title": "SECTION C — LONG QUESTIONS",
            "instruction": "Attempt the long question(s).",
            "marksLine": f"{long} question(s)",
        },
    }
