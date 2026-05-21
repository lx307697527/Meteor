"""UIAutomation Value Pattern output."""

from __future__ import annotations

import logging

logger = logging.getLogger("voiceime.output.uia")


def try_uia_output(text: str) -> bool:
    """Try to inject text via UIAutomation Value Pattern.

    Returns True if successful, False otherwise.
    This is a best-effort approach — only works with Win32/WPF text controls.
    """
    try:
        import ctypes
        from ctypes import wintypes

        # Use comtypes for UIAutomation if available
        try:
            import comtypes.client

            uia = comtypes.client.CreateObject(
                "{ff48dba4-60ef-4201-aa87-54103eef594e}",
                interface=comtypes.gen.UIAutomationClient.IUIAutomation,
            )
            element = uia.GetFocusedElement()
            if not element:
                return False

            value_pattern = element.GetCurrentPattern(
                uia.LookupId(10002)  # UIA_ValuePatternId
            )
            if value_pattern:
                value_pattern.QueryInterface(
                    comtypes.gen.UIAutomationClient.IUIAutomationValuePattern
                )
                value_pattern.SetValue(text)
                return True
        except (ImportError, Exception):
            pass

        return False
    except Exception as exc:
        logger.debug("UIA output failed: %s", exc)
        return False
