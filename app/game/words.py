from functools import cache
from pathlib import Path

from app import configs


@cache
def load_words(path: str | None = None) -> frozenset[str]:
    source = Path(path) if path else configs.WORDS_FILE
    return frozenset(
        line.strip().lower()
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip().isalpha()
        and configs.MIN_WORD_LENGTH <= len(line.strip()) <= configs.MAX_WORD_LENGTH
    )


def normalize_letters(value: str, *, min_length: int | None = None, max_length: int | None = None) -> str:
    """Normalise a letter pool to unique uppercase letters."""
    minimum = configs.MIN_LETTERS if min_length is None else min_length
    maximum = configs.MAX_LETTERS if max_length is None else max_length
    letters = "".join(ch for ch in str(value or "").strip().upper() if ch.isascii() and ch.isalpha())
    if not minimum <= len(letters) <= maximum:
        raise ValueError(f"letters must contain {minimum} to {maximum} characters")
    if len(set(letters)) != len(letters):
        raise ValueError("letters must not contain duplicates")
    return letters


def is_valid_word(word: str, letters: str, words: frozenset[str] | None = None) -> bool:
    """Check a submitted word against the dictionary and the round's letters.

    Letters may be reused inside a word (so "tree" is valid); only the pool of
    allowed letters is enforced.  Words are checked against the offline English
    dictionary so non-English input cannot earn points or deal damage.
    """
    candidate = (word or "").strip().lower()
    if not candidate.isascii() or not candidate.isalpha():
        return False
    if not configs.MIN_WORD_LENGTH <= len(candidate) <= configs.MAX_WORD_LENGTH:
        return False
    if not set(candidate).issubset(set((letters or "").lower())):
        return False
    return candidate in (words if words is not None else load_words())
