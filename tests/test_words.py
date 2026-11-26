import pytest

from app.game.words import is_valid_word, load_words, normalize_letters


def test_dictionary_and_letters():
    words = load_words()
    assert "cat" in words
    assert "spell" in words
    assert is_valid_word("cat", "AEIOURSTLNCD", words)
    assert is_valid_word("spelt", "SPELTABC", words)
    assert not is_valid_word("level", "AEIOURSTLNCD", words)
    assert not is_valid_word("cat", "XYZABDE", words)
    assert not is_valid_word("ca", "AEIOURSTLNCD", words)


def test_dictionary_contains_long_and_modern_words():
    words = load_words()
    for word in ["congratulations", "extraordinary", "responsibility", "international"]:
        assert word in words
    for word in ["blockchain", "selfie", "emoji", "podcast", "smartphone", "website", "javascript"]:
        assert word in words
    assert all(word.isascii() and word.isalpha() for word in list(words)[:1000])
    assert all(3 <= len(word) <= 15 for word in list(words)[:1000])


def test_normalize_letters():
    assert normalize_letters("a b c d e f") == "ABCDEF"
    with pytest.raises(ValueError):
        normalize_letters("ab")
    with pytest.raises(ValueError):
        normalize_letters("abcabc")
