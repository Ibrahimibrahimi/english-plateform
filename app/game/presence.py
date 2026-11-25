import time

from app import configs

_last_seen: dict[int, float] = {}


def touch(user_id: int) -> None:
    _last_seen[user_id] = time.monotonic()


def online_ids() -> list[int]:
    cutoff = time.monotonic() - configs.PRESENCE_TIMEOUT_SECONDS
    return [uid for uid, seen in _last_seen.items() if seen >= cutoff]
