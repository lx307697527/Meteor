"""CONTRACT-05: OutputProvider protocol compliance."""

from unittest.mock import MagicMock, patch

import pytest

from voiceime.protocols import OutputProvider, OutputResult


class TestContractOutputProvider:
    """Verify OutputController satisfies OutputProvider protocol."""

    def test_should_satisfy_protocol_interface(self):
        from voiceime.output.controller import OutputController

        ctrl = OutputController()
        assert isinstance(ctrl, OutputProvider)

    def test_should_return_output_result_with_required_fields(self):
        from voiceime.output.controller import OutputController

        ctrl = OutputController()
        with patch.object(ctrl._guard, "backup", return_value=None), \
             patch.object(ctrl._guard, "write_and_paste", return_value=True), \
             patch.object(ctrl._guard, "restore"):
            result = ctrl.output("test")
        assert isinstance(result, OutputResult)
        assert hasattr(result, "success")
        assert hasattr(result, "method")
        assert hasattr(result, "error")

    def test_should_follow_fallback_order(self):
        from voiceime.output.controller import OutputController

        ctrl = OutputController()
        call_log = []

        with patch.object(ctrl._guard, "backup", return_value=None), \
             patch.object(ctrl._guard, "write_and_paste", side_effect=lambda t: (call_log.append("clipboard") or False)), \
             patch("voiceime.output.controller.try_uia_output", side_effect=lambda t: (call_log.append("uia") or False)), \
             patch("voiceime.output.controller.type_text", side_effect=lambda t: (call_log.append("keyboard") or True)):
            ctrl.output("test")

        assert call_log == ["clipboard", "uia", "keyboard"]
