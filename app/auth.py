import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app import config
from app.db import SessionLocal
from app.models import User

COOKIE_NAME = "sb_session"
_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="spellbattle-session")
_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest)
    except (ValueError, AttributeError):
        return False


def make_token(user_id: int) -> str:
    return _serializer.dumps(user_id)


def read_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=config.SESSION_MAX_AGE)
    except (BadSignature, ValueError, TypeError):
        return None


def set_session(response: Response, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        make_token(user_id),
        max_age=config.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


def current_user(request: Request) -> User | None:
    user_id = read_token(request.cookies.get(COOKIE_NAME))
    if user_id is None:
        return None
    db = SessionLocal()
    try:
        return db.get(User, user_id)
    finally:
        db.close()


def require_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def require_admin(request: Request) -> User:
    user = require_user(request)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "lifetime_learning_points": user.lifetime_learning_points,
        "wins": user.wins,
        "losses": user.losses,
        "tournaments_played": user.tournaments_played,
    }
