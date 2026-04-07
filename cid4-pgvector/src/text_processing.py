from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

BASE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}

CHEMISTRY_ALLOWLIST = {
    "1-amino-2-propanol",
    "1-amino-propan-2-ol",
    "aminoacetone",
    "cid",
    "doi",
    "er-alpha",
    "fungicide",
    "glutathione",
    "ic50",
    "isopropanolamine",
    "metabolism",
    "nadh",
    "nad+",
    "pmid",
    "sid",
    "tox21",
}

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[+\-/][A-Za-z0-9]+)*")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&gt;", ">")
    text = text.replace("&lt;", "<")
    text = text.replace("μ", "u")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize_preserving_chemistry(text: str) -> list[str]:
    normalized = normalize_text(text)
    return TOKEN_PATTERN.findall(normalized)


def lowercase_tokens(tokens: Iterable[str]) -> list[str]:
    return [token.lower() for token in tokens if token]


def filter_stopwords(
    tokens: Iterable[str], stopwords: set[str] | None = None
) -> list[str]:
    vocabulary = BASE_STOPWORDS if stopwords is None else stopwords
    filtered: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in CHEMISTRY_ALLOWLIST:
            filtered.append(lowered)
            continue
        if lowered in vocabulary:
            continue
        filtered.append(lowered)
    return filtered
