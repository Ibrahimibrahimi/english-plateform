from functools import cache
from pathlib import Path

from app import config


@cache
def load_words(path: str | None = None) -> frozenset[str]:
    source = Path(path) if path else config.WORDS_FILE
    return frozenset(
        line.strip().lower()
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip().isalpha() and config.MIN_WORD_LENGTH <= len(line.strip()) <= config.MAX_WORD_LENGTH
    )


def normalize_letters(value: str) -> str:
    letters = "".join(ch for ch in value.strip().upper() if ch.isalpha())
    if not config.MIN_LETTERS <= len(letters) <= config.MAX_LETTERS:
        raise ValueError(f"letters must contain {config.MIN_LETTERS} to {config.MAX_LETTERS} characters")
    if len(set(letters)) != len(letters):
        raise ValueError("letters must not contain duplicates")
    return letters


def is_valid_word(word: str, letters: str, words: frozenset[str] | None = None) -> bool:
    candidate = (word or "").strip().lower()
    if not candidate.isascii() or not candidate.isalpha():
        return False
    if not config.MIN_WORD_LENGTH <= len(candidate) <= config.MAX_WORD_LENGTH:
        return False
    if len(set(candidate)) != len(candidate):
        return False
    if not set(candidate).issubset(set(letters.lower())):
        return False
    return candidate in (words if words is not None else load_words())
