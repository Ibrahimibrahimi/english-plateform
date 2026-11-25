"""Input validation helpers used by every public endpoint.

All user supplied text is normalised, length-limited and (where possible)
restricted to a safe character set before it reaches the database.  Database
access itself always goes through SQLAlchemy bound parameters, so user input is
never concatenated into SQL.
"""

import re

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


def clean_avatar(value) -> str:
    """Return a known avatar key, falling back to the configured default."""
    key = clean_text(value, configs.KEY_MAX_LENGTH)
    return key if key in configs.AVATARS else configs.DEFAULT_AVATAR
