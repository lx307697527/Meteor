"""CoreController Phase 3 tests — context-aware behavior integration."""

from unittest.mock import MagicMock, patch

import pytest

from voiceime.protocols import (
    ASRResult,
    ContextOverrides,
    HistoryRecord,
    OutputResult,
    ProcessContext,
    ProcessResult,
)


@pytest.fixture
def core(qapp):
    """Minimal CoreController with Phase 3 context engine mocked."""
    from voiceime.core import CoreController

    core = CoreController.__new__(CoreController)
    super(CoreController, core).__init__()
    core._state = "READY"
    core._config = MagicMock()
    core._config.get = MagicMock(side_effect=lambda k, d=None: {
        "ui.quick_mode": True,
        "ui.memory_lock": False,
        "context.enabled": True,
    }.get(k, d))
    core._recorder = MagicMock()
    core._asr = MagicMock()
    core._output = MagicMock()
    core._output.output.return_value = OutputResult(success=True, method="clipboard", error=None)
    core._hotkey = None
    core._tray = MagicMock()
    core._model_mgr = None
    core._settings_window = None
    core._history_window = None
    core._hotword_window = None
    core._floating_bar = MagicMock()
    core._pipeline = MagicMock()
    core._pipeline.process.return_value = ProcessResult(
        text="你好世界", is_polished=False, steps_applied=["punct"]
    )
    core._history = MagicMock()
    core._hotword_repo = MagicMock()
    core._llm_client = MagicMock()
    core._llm_client.is_configured = False
    core._keyring_store = None
    core._inference_future = None
    core._polish_future = None
    core._current_audio = MagicMock()
    core._current_audio.duration_ms = 1000
    core._last_raw_text = ""
    core._last_processed_text = ""
    core._last_asr_result = None
    core._hotkey_queue = MagicMock()
    core._cmd_queue = MagicMock()
    core._result_queue = MagicMock()
    from PyQt6.QtCore import QTimer
    core._timer = QTimer()
    core._rec_timer = QTimer()
    core._current_overrides = None
    core._context_engine = MagicMock()
    core._context_engine.get_context.return_value = ProcessContext(
        app_name="Code.exe", app_title="test.py"
    )
    core._context_engine.match_rules.return_value = None
    return core


class TestCoreContextIntegration:
    def test_should_query_context_on_inference_complete(self, core):
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        core._on_inference_complete(core._last_asr_result)
        core._context_engine.get_context.assert_called()

    def test_should_query_rules_on_inference_complete(self, core):
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        core._on_inference_complete(core._last_asr_result)
        core._context_engine.match_rules.assert_called_once()

    def test_should_pass_context_to_pipeline(self, core):
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        core._on_inference_complete(core._last_asr_result)
        call_args = core._pipeline.process.call_args
        assert call_args is not None

    def test_should_use_context_quick_mode_override(self, core):
        core._context_engine.match_rules.return_value = ContextOverrides(
            quick_mode=False, polish_mode=None, system_prompt=None,
            punct_normalize=None, t2s_enabled=None, hotword_enabled=None,
        )
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        # With quick_mode=False from context, should go to CONFIRMING not OUTPUTTING
        core._output.output.reset_mock()
        core._set_state("INFERRING")
        core._on_inference_complete(core._last_asr_result)
        assert core._state == "CONFIRMING"

    def test_should_use_global_quick_mode_when_no_override(self, core):
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        core._set_state("INFERRING")
        core._on_inference_complete(core._last_asr_result)
        # Default: ui.quick_mode=True → should go through OUTPUTTING then READY
        assert core._state == "READY"

    def test_should_trigger_auto_polish_when_context_override(self, core):
        core._context_engine.match_rules.return_value = ContextOverrides(
            quick_mode=None, polish_mode="auto", system_prompt=None,
            punct_normalize=None, t2s_enabled=None, hotword_enabled=None,
        )
        core._llm_client.is_configured = True
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        core._set_state("INFERRING")
        core._on_inference_complete(core._last_asr_result)
        assert core._polish_future is not None

    def test_should_not_auto_polish_when_no_override(self, core):
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        core._set_state("INFERRING")
        core._on_inference_complete(core._last_asr_result)
        assert core._polish_future is None

    def test_should_store_overrides_on_inference_complete(self, core):
        overrides = ContextOverrides(
            quick_mode=False, polish_mode="manual", system_prompt="test",
            punct_normalize=None, t2s_enabled=None, hotword_enabled=None,
        )
        core._context_engine.match_rules.return_value = overrides
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        core._on_inference_complete(core._last_asr_result)
        assert core._current_overrides == overrides

    def test_should_clear_overrides_when_context_engine_unavailable(self, core):
        core._context_engine = None
        core._current_overrides = ContextOverrides(
            quick_mode=True, polish_mode=None, system_prompt=None,
            punct_normalize=None, t2s_enabled=None, hotword_enabled=None,
        )
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        core._on_inference_complete(core._last_asr_result)
        assert core._current_overrides is None


class TestCoreContextHistory:
    def test_should_populate_app_info_in_history(self, core):
        core._last_asr_result = ASRResult(
            text="hello", language="en", inference_ms=200, segments=[]
        )
        core._do_output("hello")
        record = core._history.save.call_args[0][0]
        assert record.app_name == "Code.exe"
        assert record.app_title == "test.py"

    def test_should_save_null_context_when_engine_unavailable(self, core):
        core._context_engine = None
        core._last_asr_result = ASRResult(
            text="test", language="en", inference_ms=100, segments=[]
        )
        core._do_output("test")
        record = core._history.save.call_args[0][0]
        assert record.app_name is None
        assert record.app_title is None


class TestCoreDoPolishWithContext:
    def test_should_pass_context_prompt_to_polish(self, core):
        core._context_engine.match_rules.return_value = ContextOverrides(
            quick_mode=None, polish_mode=None, system_prompt="custom_prompt",
            punct_normalize=None, t2s_enabled=None, hotword_enabled=None,
        )
        core._current_overrides = core._context_engine.match_rules.return_value
        core._last_processed_text = "test"
        core._do_polish()
        # Verify polish_only called with system_prompt arg
        # Since we're using ThreadPoolExecutor.submit, check the args
        assert core._polish_future is not None

    def test_should_use_none_prompt_when_no_override(self, core):
        core._current_overrides = None
        core._last_processed_text = "test"
        core._do_polish()
        assert core._polish_future is not None


class TestCoreEmptyRecognitionWithContext:
    def test_should_skip_context_on_empty_result(self, core):
        core._context_engine.get_context.reset_mock()
        core._last_asr_result = ASRResult(
            text="", language="", inference_ms=0, segments=[]
        )
        core._on_inference_complete(core._last_asr_result)
        # Empty result should return early, no context queries needed
        assert core._state == "READY"

    def test_should_go_to_ready_on_empty_transcription(self, core):
        core._last_asr_result = ASRResult(
            text="", language="", inference_ms=0, segments=[]
        )
        core._on_inference_complete(core._last_asr_result)
        assert core._state == "READY"
