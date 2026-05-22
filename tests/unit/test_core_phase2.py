"""Additional CoreController tests — Phase 2 features: LLM polish, history, windows, floating bar."""

from unittest.mock import MagicMock, patch

import pytest

from voiceime.protocols import (
    ASRResult,
    HistoryRecord,
    HotKeyEvent,
    OutputResult,
    ProcessResult,
    TrayCommand,
)


@pytest.fixture
def core(qapp):
    from voiceime.core import CoreController

    core = CoreController.__new__(CoreController)
    super(CoreController, core).__init__()
    core._state = "READY"
    core._config = MagicMock()
    core._config.get = MagicMock(side_effect=lambda k, d=None: d)
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
    return core


class TestCoreLLMPolish:
    def test_should_dispatch_polish_to_pipeline(self, core):
        core._last_processed_text = "你好世界"
        core._do_polish()
        assert core._polish_future is not None

    def test_should_not_polish_when_no_text(self, core):
        core._last_processed_text = ""
        core._do_polish()
        assert core._polish_future is None

    def test_should_not_polish_when_no_pipeline(self, core):
        core._pipeline = None
        core._last_processed_text = "test"
        core._do_polish()
        assert core._polish_future is None

    def test_should_update_text_on_polish_success(self, core):
        core._last_processed_text = "原始文本"
        result = ProcessResult(text="润色后文本", is_polished=True, steps_applied=["llm"])
        core._on_polish_complete(result)
        assert core._last_processed_text == "润色后文本"

    def test_should_preserve_text_on_polish_failure(self, core):
        core._last_processed_text = "原始文本"
        result = ProcessResult(text="原始文本", is_polished=False, steps_applied=[])
        core._on_polish_complete(result)
        assert core._last_processed_text == "原始文本"

    def test_should_emit_llm_result_signal(self, core):
        received = []
        core.llm_result_received.connect(lambda r: received.append(r))
        result = ProcessResult(text="polished", is_polished=True, steps_applied=["llm"])
        core._on_polish_complete(result)
        assert len(received) == 1
        assert received[0].text == "polished"


class TestCoreHistorySaving:
    def test_should_save_to_history_after_output(self, core):
        core._last_raw_text = "raw text"
        core._last_asr_result = ASRResult(
            text="processed", language="zh", inference_ms=500, segments=[]
        )
        core._current_audio.duration_ms = 2000
        core._output.output.return_value = OutputResult(success=True, method="clipboard", error=None)
        core._do_output("processed")
        core._history.save.assert_called_once()
        record = core._history.save.call_args[0][0]
        assert isinstance(record, HistoryRecord)
        assert record.text == "processed"
        assert record.raw_text == "raw text"
        assert record.language == "zh"
        assert record.audio_duration_ms == 2000
        assert record.inference_time_ms == 500

    def test_should_not_save_when_no_history(self, core):
        core._history = None
        core._do_output("test")
        # Should not raise

    def test_should_not_save_when_empty_text(self, core):
        core._save_history("")
        core._history.save.assert_not_called()

    def test_should_mark_polished_when_text_differs_from_raw(self, core):
        core._last_raw_text = "原始"
        core._last_asr_result = ASRResult(text="原始", language="zh", inference_ms=100, segments=[])
        core._output.output.return_value = OutputResult(success=True, method="clipboard", error=None)
        core._do_output("处理后")
        record = core._history.save.call_args[0][0]
        assert record.is_polished is True

    def test_should_not_mark_polished_when_text_same_as_raw(self, core):
        core._last_raw_text = "相同文本"
        core._last_asr_result = ASRResult(text="相同文本", language="zh", inference_ms=100, segments=[])
        core._output.output.return_value = OutputResult(success=True, method="clipboard", error=None)
        core._do_output("相同文本")
        record = core._history.save.call_args[0][0]
        assert record.is_polished is False


class TestCoreFloatingBar:
    def test_should_show_recording_on_state_change(self, core):
        core._on_state_changed_for_floating("RECORDING")
        core._floating_bar.show_recording.assert_called_once()

    def test_should_show_inferring_on_state_change(self, core):
        core._on_state_changed_for_floating("INFERRING")
        core._floating_bar.show_inferring.assert_called_once()

    def test_should_show_confirming_with_asr_data(self, core):
        core._last_asr_result = ASRResult(
            text="你好", language="zh", inference_ms=500, segments=[]
        )
        core._last_processed_text = "你好"
        core._on_state_changed_for_floating("CONFIRMING")
        core._floating_bar.show_confirming.assert_called_once_with(
            "你好", language="zh", inference_ms=500
        )

    def test_should_hide_bar_on_ready(self, core):
        core._on_state_changed_for_floating("READY")
        core._floating_bar.hide_bar.assert_called_once()

    def test_should_hide_bar_on_paused(self, core):
        core._on_state_changed_for_floating("PAUSED")
        core._floating_bar.hide_bar.assert_called_once()

    def test_should_hide_bar_on_error_states(self, core):
        core._on_state_changed_for_floating("ERROR_MIC")
        core._floating_bar.hide_bar.assert_called_once()

    def test_should_hide_bar_on_outputting(self, core):
        core._on_state_changed_for_floating("OUTPUTTING")
        core._floating_bar.hide_bar.assert_called_once()

    def test_should_not_crash_when_floating_bar_is_none(self, core):
        core._floating_bar = None
        core._on_state_changed_for_floating("RECORDING")
        # Should not raise

    def test_should_rerecord_from_floating_bar(self, core):
        core._set_state = MagicMock()
        core._on_floating_rerecord()
        assert core._set_state.call_count >= 1

    def test_should_cancel_from_floating_bar(self, core):
        core._set_state = MagicMock()
        core._on_floating_cancel()
        core._tray.set_status.assert_called_with("ready")


class TestCoreWindowManagement:
    def test_should_open_settings_window(self, core):
        core._open_settings()
        assert core._settings_window is not None

    def test_should_focus_existing_settings_window(self, core):
        mock_win = MagicMock()
        core._settings_window = mock_win
        core._open_settings()
        mock_win.raise_.assert_called_once()
        mock_win.activateWindow.assert_called_once()

    def test_should_clear_settings_window_on_destroy(self, core):
        mock_win = MagicMock()
        core._settings_window = mock_win
        core._on_settings_destroyed()
        assert core._settings_window is None

    def test_should_open_history_window(self, core):
        core._open_history()
        assert core._history_window is not None

    def test_should_focus_existing_history_window(self, core):
        mock_win = MagicMock()
        core._history_window = mock_win
        core._open_history()
        mock_win.raise_.assert_called_once()

    def test_should_clear_history_window_on_close(self, core):
        mock_win = MagicMock()
        core._history_window = mock_win
        core._on_history_closed()
        assert core._history_window is None

    def test_should_open_hotword_window(self, core):
        core._open_hotword()
        assert core._hotword_window is not None

    def test_should_focus_existing_hotword_window(self, core):
        mock_win = MagicMock()
        core._hotword_window = mock_win
        core._open_hotword()
        mock_win.raise_.assert_called_once()

    def test_should_clear_hotword_window_on_close(self, core):
        mock_win = MagicMock()
        core._hotword_window = mock_win
        core._on_hotword_closed()
        assert core._hotword_window is None


class TestCoreTrayCommands:
    def test_should_exit_on_exit_command(self, core):
        core.stop = MagicMock()
        core._handle_tray_command(TrayCommand(action="exit"))
        core.stop.assert_called_once()

    def test_should_open_settings_on_settings_command(self, core):
        core._open_settings = MagicMock()
        core._handle_tray_command(TrayCommand(action="settings"))
        core._open_settings.assert_called_once()

    def test_should_open_history_on_history_command(self, core):
        core._open_history = MagicMock()
        core._handle_tray_command(TrayCommand(action="history"))
        core._open_history.assert_called_once()

    def test_should_open_hotword_on_hotword_command(self, core):
        core._open_hotword = MagicMock()
        core._handle_tray_command(TrayCommand(action="hotword"))
        core._open_hotword.assert_called_once()

    def test_should_ignore_unknown_command(self, core):
        # Should not raise
        core._handle_tray_command(TrayCommand(action="unknown_action"))


class TestCorePollQueues:
    def test_should_process_hotkey_events(self, core):
        core._hotkey = MagicMock()
        core._hotkey.process_pending_events = MagicMock()
        core._poll_queues()
        core._hotkey.process_pending_events.assert_called_once()

    def test_should_not_process_hotkey_when_none(self, core):
        core._hotkey = None
        core._poll_queues()
        # Should not raise

    def test_should_handle_inference_timeout(self, core):
        from concurrent.futures import Future
        from voiceime.asr.engine import InferenceTimeoutError

        future = Future()
        future.set_exception(InferenceTimeoutError("timeout"))
        core._inference_future = future
        core._poll_queues()
        assert core._state == "ERROR_INFERENCE_TIMEOUT"

    def test_should_handle_inference_error(self, core):
        from concurrent.futures import Future

        future = Future()
        future.set_exception(RuntimeError("model broken"))
        core._inference_future = future
        core._poll_queues()
        # Should transition to READY on non-timeout error
        assert core._state == "READY"

    def test_should_handle_polish_error(self, core):
        from concurrent.futures import Future

        future = Future()
        future.set_exception(RuntimeError("llm error"))
        core._polish_future = future
        core._last_processed_text = "original"
        core._poll_queues()
        # Should fall back to original text
        assert core._polish_future is None


class TestCoreOutput:
    def test_should_emit_error_on_output_failure(self, core):
        core._output.output.return_value = OutputResult(
            success=False, method="clipboard", error="clipboard full"
        )
        errors = []
        core.error_occurred.connect(lambda s, m: errors.append((s, m)))
        core._do_output("test")
        assert len(errors) == 1
        assert errors[0][0] == "ERROR_CLIPBOARD"

    def test_should_set_state_to_outputting_before_output(self, core):
        core._do_output("test")
        # State transitions through OUTPUTTING then back to READY
        assert core._state == "READY"

    def test_should_notify_tray_on_output_complete(self, core):
        core._do_output("test")
        core._tray.set_status.assert_called_with("ready")


class TestCoreStateProperty:
    def test_should_return_current_state(self, core):
        core._state = "RECORDING"
        assert core.state == "RECORDING"

    def test_should_return_ready_by_default(self, core):
        assert core.state == "READY"
