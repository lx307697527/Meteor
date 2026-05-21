"""OutputController — three-layer fallback text output."""

from __future__ import annotations

import logging

from voiceime.output.clipboard import ClipboardGuard
from voiceime.output.keyboard import type_text
from voiceime.output.uia import try_uia_output
from voiceime.protocols import OutputResult

logger = logging.getLogger("voiceime.output.controller")


class OutputController:
    """Outputs text to the focused window with three-layer fallback."""

    def __init__(self, clipboard_delay_ms: int = 50) -> None:
        self._guard = ClipboardGuard(restore_delay_ms=clipboard_delay_ms)

    def output(self, text: str) -> OutputResult:
        """Output text using three-layer fallback: clipboard → UIA → keyboard."""
        if not text:
            return OutputResult(success=False, method="", error="Empty text")

        # Layer 1: Clipboard + Ctrl+V
        backup = self._guard.backup()
        if self._guard.write_and_paste(text):
            self._guard.restore(backup)
            logger.info("Output via clipboard: %d chars", len(text))
            return OutputResult(success=True, method="clipboard", error=None)

        logger.warning("Clipboard method failed, trying UIA")

        # Layer 2: UIAutomation Value Pattern
        if try_uia_output(text):
            logger.info("Output via UIA: %d chars", len(text))
            return OutputResult(success=True, method="uia", error=None)

        logger.warning("UIA method failed, trying keyboard fallback")

        # Layer 3: Keyboard character-by-character
        if type_text(text):
            logger.info("Output via keyboard: %d chars", len(text))
            return OutputResult(success=True, method="keyboard", error=None)

        return OutputResult(
            success=False, method="", error="All output methods failed"
        )
