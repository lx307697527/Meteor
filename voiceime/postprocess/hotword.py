"""Hotword replacement — apply user-defined word replacements."""

from __future__ import annotations

from voiceime.protocols import HotwordProvider


def apply_hotwords(text: str, provider: HotwordProvider) -> str:
    """Replace all hotword triggers found in text using the provider."""
    if not text or not provider:
        return text

    result = text
    for entry in provider.list_all():
        trigger = entry.get("trigger", "")
        replace = entry.get("replace", "")
        case_sensitive = entry.get("case_sensitive", False)
        if not trigger or not replace:
            continue
        if case_sensitive:
            result = result.replace(trigger, replace)
        else:
            result = _replace_case_insensitive(result, trigger, replace)
    return result


def _replace_case_insensitive(text: str, trigger: str, replace: str) -> str:
    import re
    return re.sub(re.escape(trigger), replace, text, flags=re.IGNORECASE)
