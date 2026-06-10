from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import TranscriptRecord


def save_transcript(
    transcript_text,
    *,
    user_id=None,
    input_type="youtube",
    source_label="",
    source_engine="",
    word_count=0,
):
    init_db()
    db = SessionLocal()
    try:
        row = TranscriptRecord(
            user_id=user_id,
            input_type=input_type,
            source_label=(source_label or "")[:500],
            source_engine=(source_engine or "")[:40],
            word_count=word_count or len((transcript_text or "").split()),
            transcript_text=transcript_text or "",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def transcript_to_dict(row, include_text=False):
    data = {
        "id": row.id,
        "userId": row.user_id,
        "inputType": row.input_type,
        "sourceLabel": row.source_label,
        "sourceEngine": row.source_engine,
        "wordCount": row.word_count,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }
    if include_text:
        data["transcript"] = row.transcript_text
    else:
        preview = (row.transcript_text or "")[:200]
        data["preview"] = preview + ("…" if len(row.transcript_text or "") > 200 else "")
    return data
