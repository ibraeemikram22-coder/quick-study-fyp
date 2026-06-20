"""Punjab Board subject-specific pre-board patterns (from official paper layouts)."""

SCIENCE_SUBJECTS = frozenset({"Physics", "Chemistry", "Biology"})
COMPUTER_SUBJECTS = frozenset({"Computer", "Computer Science"})


def subject_group(subject_name):
    name = (subject_name or "").strip()
    if name in SCIENCE_SUBJECTS:
        return "science"
    if name in COMPUTER_SUBJECTS:
        return "computer"
    return "english"


# Pre-board subjective layout (after objective MCQ section)
PRE_BOARD_LAYOUT = {
    "science": {
        "mcq": 17,
        "short_count": 33,
        "long_count": 5,
        "short_attempt": 22,
        "long_attempt": 3,
        "total_marks": 85,
        "duration": "3 Hours",
        "short_blocks": [
            {"questionNo": 2, "printed": 12, "attempt": 8, "marks_each": 2},
            {"questionNo": 3, "printed": 12, "attempt": 8, "marks_each": 2},
            {"questionNo": 4, "printed": 9, "attempt": 6, "marks_each": 2},
        ],
        "long_marks_each": 8,
        "long_has_parts": True,
    },
    "computer": {
        "mcq": 15,
        "short_count": 27,
        "long_count": 5,
        "short_attempt": 18,
        "long_attempt": 3,
        "total_marks": 75,
        "duration": "2:40 Hours",
        "short_blocks": [
            {"questionNo": 2, "printed": 9, "attempt": 6, "marks_each": 2},
            {"questionNo": 3, "printed": 9, "attempt": 6, "marks_each": 2},
            {"questionNo": 4, "printed": 9, "attempt": 6, "marks_each": 2},
        ],
        "long_marks_each": 8,
        "long_has_parts": False,
    },
}


def apply_subject_pattern(exam_code, subject_name, base_counts):
    """Merge DB pattern with subject-specific Punjab pre-board rules."""
    counts = dict(base_counts)
    code = (exam_code or "").lower()
    if code != "pre_board":
        return counts

    group = subject_group(subject_name)
    if group == "english":
        return counts

    layout = PRE_BOARD_LAYOUT.get(group)
    if not layout:
        return counts

    counts["mcq"] = layout["mcq"]
    counts["short"] = layout["short_count"]
    counts["long"] = layout["long_count"]
    counts["marks"] = layout["total_marks"]
    counts["duration"] = layout["duration"]
    counts["short_attempt"] = layout["short_attempt"]
    counts["long_attempt"] = layout["long_attempt"]
    counts["subject_group"] = group
    counts["short_blocks"] = layout["short_blocks"]
    counts["long_marks_each"] = layout["long_marks_each"]
    counts["long_has_parts"] = layout["long_has_parts"]
    return counts


def bulk_gen_counts_for_subject(subject_name):
    """Per-chapter AI generation targets so pre-board papers can be built."""
    group = subject_group(subject_name)
    if group == "computer":
        return {"mcq": 10, "short": 10, "long": 3}
    if group == "science":
        return {"mcq": 12, "short": 12, "long": 3}
    return {"mcq": 8, "short": 6, "long": 2}
