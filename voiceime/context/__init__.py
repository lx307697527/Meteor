"""Context-aware behavior — window detection and rule matching."""

from voiceime.context.engine import ContextEngine
from voiceime.context.rules import ContextRuleRepo
from voiceime.context.window import WindowInfo, get_foreground_window

__all__ = ["ContextEngine", "ContextRuleRepo", "WindowInfo", "get_foreground_window"]
