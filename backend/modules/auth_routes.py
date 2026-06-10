from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import User

auth_bp = Blueprint("auth", __name__)

ROLES = ("student", "teacher", "admin")


def _user_public(row):
    return {"id": row.id, "name": row.name, "email": row.email, "role": row.role}


@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    init_db()
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    role = (body.get("role") or "student").lower().strip()
    if not name or not email or not password:
        return jsonify({"success": False, "error": "Name, email and password required"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400
    if role not in ROLES:
        role = "student"
    if role == "admin":
        return jsonify(
            {"success": False, "error": "Admin accounts cannot be created from signup."}
        ), 403
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            return jsonify({"success": False, "error": "Email already registered"}), 400
        row = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(
            {"success": True, "message": "Account created.", "user": _user_public(row)}
        )
    finally:
        db.close()


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    init_db()
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required"}), 400
    db = SessionLocal()
    try:
        row = db.query(User).filter(User.email == email).first()
        if not row or not check_password_hash(row.password_hash, password):
            return jsonify({"success": False, "error": "Invalid email or password"}), 401
        return jsonify({"success": True, "user": _user_public(row)})
    finally:
        db.close()
