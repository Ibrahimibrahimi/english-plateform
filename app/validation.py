"""Input validation helpers used by every public endpoint.

All user supplied text is normalised, length-limited and (where possible)
restricted to a safe character set before it reaches the database.  Database
access itself always goes through SQLAlchemy bound parameters, so user input is
never concatenated into SQL.
"""

import re
from pathlib import Path

from app import configs

_KEY_PATTERN = re.compile(rf"^[A-Z0-9]{{1,{configs.KEY_MAX_LENGTH}}}$")


class ConflictError(ValueError):
    """A validation error that should be returned to the client as HTTP 409."""


def clean_text(value, max_length: int, *, required: bool = False, label: str = "Value") -> str:
    """Return a printable, length-limited string.

    Control characters are stripped (this also removes NUL bytes and newlines
    that could be used to smuggle SQL or log entries), surrounding whitespace
    is trimmed and an optional non-empty check is applied.
    """
    text = str(value or "")
    text = "".join(ch for ch in text if ch.isprintable())
    text = text.strip()
    if required and not text:
        raise ValueError(f"{label} is required")
    return text[:max_length]


def clean_key(value) -> str:
    """Validate a shareable challenge/tournament key."""
    key = clean_text(value, configs.KEY_MAX_LENGTH).upper()
    if not _KEY_PATTERN.fullmatch(key):
        raise ValueError("Invalid key")
    return key


def clean_search(value) -> str:
    """Validate a free-text search term and escape LIKE wildcards."""
    term = clean_text(value, configs.SEARCH_MAX_LENGTH)
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def parse_int(value, *, minimum: int, maximum: int, label: str, default: int | None = None) -> int:
    """Parse an integer from untrusted input within configured bounds."""
    if value is None or value == "":
        if default is None:
            raise ValueError(f"{label} is required")
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number") from None
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def parse_bool(value, *, default: bool | None = None, label: str = "Value") -> bool:
    if value is None or value == "":
        if default is None:
            raise ValueError(f"{label} is required")
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{label} must be true or false")


def clean_avatar(value) -> str:
    """Return a known avatar key, falling back to the configured default."""
    key = clean_text(value, configs.KEY_MAX_LENGTH)
    return key if key in configs.AVATARS else configs.DEFAULT_AVATAR


def _image_extension(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def clean_avatar_upload(upload) -> tuple[bytes, str]:
    """Validate an uploaded image and return its bytes with a safe extension."""
    name = getattr(upload, "filename", "") or ""
    extension = Path(name).suffix.lower().lstrip(".")
    if extension not in configs.AVATAR_UPLOAD_EXTENSIONS:
        raise ValueError("Use a PNG, JPEG, GIF or WEBP image")
    data = upload.read(configs.AVATAR_UPLOAD_MAX_BYTES + 1)
    if not data:
        raise ValueError("Choose an image to upload")
    if len(data) > configs.AVATAR_UPLOAD_MAX_BYTES:
        raise ValueError(f"Images must be smaller than {configs.AVATAR_UPLOAD_MAX_BYTES // 1024 // 1024} MB")
    detected = _image_extension(data)
    if detected is None or (detected == "jpg" and extension not in {"jpg", "jpeg"}) or (
        detected != "jpg" and detected != extension
    ):
        raise ValueError("The file does not look like a supported image")
    upload.stream.seek(0)
    return data, detected
