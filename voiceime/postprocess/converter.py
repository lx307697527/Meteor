"""Traditional ↔ Simplified Chinese conversion via opencc."""

from __future__ import annotations

import logging

logger = logging.getLogger("voiceime.postprocess.converter")

_t2s_converter = None
_s2t_converter = None


def _get_t2s():
    global _t2s_converter
    if _t2s_converter is None:
        try:
            from opencc import OpenCC
            _t2s_converter = OpenCC("t2s")
        except Exception as exc:
            logger.warning("opencc not available, t2s disabled: %s", exc)
    return _t2s_converter


def _get_s2t():
    global _s2t_converter
    if _s2t_converter is None:
        try:
            from opencc import OpenCC
            _s2t_converter = OpenCC("s2t")
        except Exception as exc:
            logger.warning("opencc not available, s2t disabled: %s", exc)
    return _s2t_converter


def t2s(text: str) -> str:
    """Convert Traditional Chinese to Simplified."""
    converter = _get_t2s()
    if converter is None:
        return text
    return converter.convert(text)


def s2t(text: str) -> str:
    """Convert Simplified Chinese to Traditional."""
    converter = _get_s2t()
    if converter is None:
        return text
    return converter.convert(text)
