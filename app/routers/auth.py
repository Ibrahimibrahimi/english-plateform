from flask import Blueprint, abort, g, jsonify, request

from app.auth import (
    clear_session,
    hash_password,
    public_user,
    require_user,
    set_session,
    validate_username,
    verify_password,
)
from app.game.presence import touch
from app.models import User

router = Blueprint("auth", __name__, url_prefix="/api/auth")


@router.post("/signup")
def signup():
    db = g.db
    payload = request.get_json(silent=True)
    payload = payload if isinstance(payload, dict) else {}
    try:
        username = validate_username(payload.get("username", ""))
    except ValueError as exc:
        abort(400, description=str(exc))
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if "@" not in email or not (5 <= len(email) <= 120):
        abort(400, description="Invalid email")
    if not (8 <= len(password) <= 128):
        abort(400, description="Password must be at least 8 characters")
    if db.query(User).filter(User.email == email).first():
        abort(409, description="Email already registered")
    if db.query(User).filter(User.username == username).first():
        abort(409, description="Username already taken")
    user = User(username=username, email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    response = jsonify(public_user(user))
    set_session(response, user.id)
    touch(user.id)
    return response


@router.post("/login")
def login():
    db = g.db
    payload = request.get_json(silent=True)
    payload = payload if isinstance(payload, dict) else {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(password, user.password_hash):
        abort(401, description="Invalid credentials")
    if user.status != "active":
        abort(403, description="Account is not active")
    response = jsonify(public_user(user))
    set_session(response, user.id)
    touch(user.id)
    return response


@router.post("/logout")
def logout():
    response = jsonify({"ok": True})
    clear_session(response)
    return response


@router.get("/me")
def me():
    user = require_user()
    touch(user.id)
    return jsonify(public_user(user))
