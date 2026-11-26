#!/usr/bin/env python3
"""Build the vendored English word list for SpellBattle.

Sources (all filtered to lowercase ASCII alpha, length 3-15, deduped, sorted):
- dwyl/english-words words_alpha.txt
- wordnik/wordlist wordlist-20210729.txt (MIT)
- IlyaSemenov/wikipedia-word-frequency enwiki-2023-04-13.txt top N (MIT repo)

The generated file is vendored at app/data/words.txt so runtime stays offline.
"""
from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

DWYL_URL = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"
WORDNIK_URL = "https://raw.githubusercontent.com/wordnik/wordlist/main/wordlist-20210729.txt"
WIKI_URL = "https://raw.githubusercontent.com/IlyaSemenov/wikipedia-word-frequency/master/results/enwiki-2023-04-13.txt"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "app" / "data" / "words.txt"


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=180) as response:
        return response.read().decode("utf-8", "ignore")


def parse_dwyl(text: str) -> set[str]:
    return {line.strip().lower() for line in text.splitlines() if line.strip()}


def parse_wordnik(text: str) -> set[str]:
    words: set[str] = set()
    for line in text.splitlines():
        word = line.strip().strip(",").strip().strip('"').lower()
        if word:
            words.add(word)
    return words


def parse_wiki(text: str, top_n: int) -> set[str]:
    words: set[str] = set()
    for line in text.splitlines():
        if len(words) >= top_n:
            break
        parts = line.split()
        if parts:
            words.add(parts[0].lower())
    return words


def filter_words(words: set[str], min_len: int, max_len: int) -> set[str]:
    return {
        word
        for word in words
        if word.isascii() and word.isalpha() and min_len <= len(word) <= max_len
    }


def build(min_len: int, max_len: int, top_wiki: int) -> list[str]:
    dwyl = filter_words(parse_dwyl(fetch_text(DWYL_URL)), min_len, max_len)
    wordnik = filter_words(parse_wordnik(fetch_text(WORDNIK_URL)), min_len, max_len)
    wiki = filter_words(parse_wiki(fetch_text(WIKI_URL), top_wiki), min_len, max_len)
    combined = sorted(dwyl | wordnik | wiki)
    print(f"dwyl={len(dwyl)} wordnik={len(wordnik)} wiki_top={top_wiki} wiki_filtered={len(wiki)} total={len(combined)}")
    return combined


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--min-len", type=int, default=3)
    parser.add_argument("--max-len", type=int, default=15)
    parser.add_argument("--top-wiki", type=int, default=50000)
    args = parser.parse_args()

    words = build(args.min_len, args.max_len, args.top_wiki)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(words) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
