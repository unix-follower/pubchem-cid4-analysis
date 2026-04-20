from typing import Any

from .text_utils import clean_text


def safe_int(value: Any) -> int | None:
    text = clean_text(value)
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def safe_float(value: Any) -> float | None:
    text = clean_text(value)
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None
