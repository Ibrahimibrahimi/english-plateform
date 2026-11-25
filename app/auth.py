import hashlib
import hmac
import re
import secrets

from flask import abort, g, has_request_context, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app import configs
from app.db import SessionLocal
from app.models import User

COOKIE_NAME = configs.SESSION_COOKIE_NAME
_serializer = URLSafeTimedSerializer(configs.SECRET_KEY, salt=configs.SESSION_SALT)
_ITERATIONS = configs.PASSWORD_HASH_ITERATIONS
USERNAME_PATTERN = re.compile(configs.USERNAME_PATTERN)


def validate_username(raw: str) -> str:
    username = str(raw).strip()
    if not (configs.USERNAME_MIN_LENGTH <= len(username) <= configs.USERNAME_MAX_LENGTH):
        raise ValueError(
            f"Username must be {configs.USERNAME_MIN_LENGTH}-{configs.USERNAME_MAX_LENGTH} "
            "letters, numbers, dots, dashes or underscores"
        )
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Username contains invalid characters")
    return username


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(configs.PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{configs.PASSWORD_HASH_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != configs.PASSWORD_HASH_ALGORITHM:
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
        return _serializer.loads(token, max_age=configs.SESSION_MAX_AGE)
    except (BadSignature, ValueError, TypeError):
        return None


def set_session(response, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        make_token(user_id),
        max_age=configs.SESSION_MAX_AGE,
        httponly=True,
        samesite=configs.COOKIE_SAMESITE,
        secure=configs.SESSION_COOKIE_SECURE,
    )


def clear_session(response) -> None:
    response.delete_cookie(COOKIE_NAME)


def current_user(req=None) -> User | None:
    req = req or request
    user_id = read_token(req.cookies.get(COOKIE_NAME))
    if user_id is None:
        return None
    db = getattr(g, "db", None) if has_request_context() else None
    if db is not None:
        return db.get(User, user_id)
    db = SessionLocal()
    try:
        return db.get(User, user_id)
    finally:
        db.close()


def require_user(req=None) -> User:
    req = req or request
    user = getattr(g, "current_user", None)
    if user is None:
        user = current_user(req)
    if user is None:
        abort(401, description="Login required")
    return user


def require_admin(req=None) -> User:
    user = require_user(req)
    if user.role != "admin":
        abort(403, description="Admin only")
    return user


def avatar_info(user: User) -> dict:
    """Return the configured display data for a player's chosen picture."""
    key = getattr(user, "avatar", None) or configs.DEFAULT_AVATAR
    option = configs.AVATARS.get(key, configs.AVATARS[configs.DEFAULT_AVATAR])
    image = getattr(user, "avatar_image", None)
    return {
        "key": "upload" if image else key,
        "emoji": option["emoji"],
        "color": option["color"],
        "label": "Uploaded picture" if image else option["label"],
        "image_url": f"{configs.UPLOAD_URL_PREFIX}/{image}" if image else None,
    }


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
        "avatar": avatar_info(user),
    }


def public_profile(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "lifetime_learning_points": user.lifetime_learning_points,
        "wins": user.wins,
        "losses": user.losses,
        "tournaments_played": user.tournaments_played,
        "avatar": avatar_info(user),
        "profile_url": f"/player/{user.id}",
    }
