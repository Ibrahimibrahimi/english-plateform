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


def test_normalize_letters():
    assert normalize_letters("a b c d e f") == "ABCDEF"
    with pytest.raises(ValueError):
        normalize_letters("ab")
    with pytest.raises(ValueError):
        normalize_letters("abcabc")
