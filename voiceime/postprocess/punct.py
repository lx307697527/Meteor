"""Punctuation normalization — English → Chinese punctuation in CJK context."""

from __future__ import annotations

import re

_CJK_RANGE = r"一-鿿㐀-䶿豈-﫿"

_PUNCT_MAP = {
    ",": "，",
    ".": "。",
    "?": "？",
    "!": "！",
    ":": "：",
    ";": "；",
    "(": "（",
    ")": "）",
}

# Match English punctuation preceded or followed by CJK characters
_CJK_PUNCT_PATTERN = re.compile(
    rf"(?:(?<=[{_CJK_RANGE}])\s*([,.?!:;()])\s*(?=[{_CJK_RANGE}])"
    rf"|(?<=[{_CJK_RANGE}])\s*([,.?!:;()])\s*$)"
)

# Trailing sentence particles to remove
_TRAILING_PARTICLES = re.compile(r"[啊呢吧嘛呀哦噢哇哟]+[.。!！?？]*$")


def normalize_punctuation(text: str) -> str:
    """Convert English punctuation to Chinese where surrounded by CJK text."""
    if not text:
        return text

    def _replace(match: re.Match) -> str:
        punct = match.group(1) or match.group(2)
        return _PUNCT_MAP.get(punct, punct)

    result = _CJK_PUNCT_PATTERN.sub(_replace, text)
    return result


def remove_trailing_particles(text: str) -> str:
    """Remove trailing sentence-final particles like 啊/呢/吧/嘛."""
    if not text:
        return text
    return _TRAILING_PARTICLES.sub("", text)
