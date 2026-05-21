"""OutputController unit tests — F07: three-layer fallback."""

from unittest.mock import MagicMock, patch

import pytest


class TestOutputController:
    """OutputController — clipboard → UIA → keyboard fallback chain."""

    def test_should_return_failure_when_text_is_empty(self):
        from voiceime.output.controller import OutputController

        ctrl = OutputController()
        result = ctrl.output("")
        assert result.success is False

    def test_should_succeed_with_clipboard_when_first_layer_works(self):
        from voiceime.output.controller import OutputController

        ctrl = OutputController()
        with patch.object(ctrl._guard, "backup", return_value=None), \
             patch.object(ctrl._guard, "write_and_paste", return_value=True), \
             patch.object(ctrl._guard, "restore"):
            result = ctrl.output("你好")
        assert result.success is True
        assert result.method == "clipboard"

    def test_should_fallback_to_uia_when_clipboard_fails(self):
        from voiceime.output.controller import OutputController

        ctrl = OutputController()
        with patch.object(ctrl._guard, "backup", return_value=None), \
             patch.object(ctrl._guard, "write_and_paste", return_value=False), \
             patch("voiceime.output.controller.try_uia_output", return_value=True):
            result = ctrl.output("你好")
        assert result.success is True
        assert result.method == "uia"

    def test_should_fallback_to_keyboard_when_uia_fails(self):
        from voiceime.output.controller import OutputController

        ctrl = OutputController()
        with patch.object(ctrl._guard, "backup", return_value=None), \
             patch.object(ctrl._guard, "write_and_paste", return_value=False), \
             patch("voiceime.output.controller.try_uia_output", return_value=False), \
             patch("voiceime.output.controller.type_text", return_value=True):
            result = ctrl.output("你好")
        assert result.success is True
        assert result.method == "keyboard"

    def test_should_return_failure_when_all_methods_fail(self):
        from voiceime.output.controller import OutputController

        ctrl = OutputController()
        with patch.object(ctrl._guard, "backup", return_value=None), \
             patch.object(ctrl._guard, "write_and_paste", return_value=False), \
             patch("voiceime.output.controller.try_uia_output", return_value=False), \
             patch("voiceime.output.controller.type_text", return_value=False):
            result = ctrl.output("你好")
        assert result.success is False
        assert result.error is not None
