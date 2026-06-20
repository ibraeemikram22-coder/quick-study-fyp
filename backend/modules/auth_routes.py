import os

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from modules.questionbank.db import SessionLocal, init_db
from modules.questionbank.models import User

auth_bp = Blueprint("auth", __name__)

ROLES = ("student", "teacher", "admin")


def _user_public(row):
    role = (row.role or "student").lower().strip()
    if role not in ROLES:
        role = "student"
    return {
        "id": row.id,
        "name": row.name,
        "email": row.email,
        "role": role,
    }


@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    init_db()
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    role = (body.get("role") or "student").lower().strip()
    school_name = (body.get("schoolName") or "").strip()

    if not name or not email or not password:
        return jsonify({"success": False, "error": "Name, email and password required"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400
    if role not in ROLES:
        role = "student"
    admin_email = (os.getenv("ADMIN_EMAIL") or "admin@gmail.com").strip().lower()
    if role == "admin" or email == admin_email:
        return jsonify(
            {"success": False, "error": "Cannot sign up as admin. Use Admin log in instead."}
        ), 403
    if role == "teacher":
        if not school_name:
            return jsonify(
                {"success": False, "error": "School / college name is required for teachers."}
            ), 400
        name = f"{name} — {school_name}"
    elif role != "student":
        role = "student"

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            return jsonify({"success": False, "error": "Email already registered"}), 400

        row = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            is_verified=1,
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

    if "@" not in email:
        return jsonify(
            {
                "success": False,
                "error": "Please enter a full email address (e.g. you@gmail.com).",
            }
        ), 400

    db = SessionLocal()
    try:
        row = db.query(User).filter(User.email == email).first()
        if not row:
            return jsonify(
                {
                    "success": False,
                    "error": "No account found. Please sign up first.",
                }
            ), 401
        if not check_password_hash(row.password_hash, password):
            return jsonify({"success": False, "error": "Incorrect password."}), 401

        user = _user_public(row)
        return jsonify({"success": True, "user": user, "isAdmin": row.role == "admin"})
    finally:
        db.close()


@auth_bp.route("/api/auth/verify", methods=["POST"])
def verify_session():
    """Check stored user still exists (clears stale browser sessions)."""
    init_db()
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    user_id = body.get("userId") or body.get("id")

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return jsonify({"success": True, "valid": False}), 200

    if not email:
        return jsonify({"success": True, "valid": False}), 200

    db = SessionLocal()
    try:
        row = db.query(User).filter(User.id == user_id, User.email == email).first()
        if not row:
            return jsonify({"success": True, "valid": False}), 200
        return jsonify({"success": True, "valid": True, "user": _user_public(row)})
    finally:
        db.close()


@auth_bp.route("/api/auth/profile", methods=["PATCH"])
def update_profile():
    init_db()
    body = request.get_json(silent=True) or {}
    user_id = body.get("userId") or request.headers.get("X-User-Id")
    name = (body.get("name") or "").strip()

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid user"}), 400

    if not name or len(name) < 2:
        return jsonify({"success": False, "error": "Name must be at least 2 characters"}), 400

    db = SessionLocal()
    try:
        row = db.query(User).filter(User.id == user_id).first()
        if not row:
            return jsonify({"success": False, "error": "User not found"}), 404
        if row.role == "admin":
            return jsonify({"success": False, "error": "Use admin panel to edit admin profile"}), 403

        row.name = name
        db.commit()
        db.refresh(row)
        return jsonify({"success": True, "user": _user_public(row)})
    finally:
        db.close()
