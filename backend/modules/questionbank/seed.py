"""First-run seed — Punjab Board only (no Federal / PTB)."""
from .db import SessionLocal, init_db
from .models import Board
from .punjab_seed import ensure_punjab_data


def run_seed():
    init_db()
    db = SessionLocal()
    try:
        if db.query(Board).filter(Board.code == "punjab").first():
            return False
    finally:
        db.close()
    ensure_punjab_data(add_demo_chapters=False)
    return True
