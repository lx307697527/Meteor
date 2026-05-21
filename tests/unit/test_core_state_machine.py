"""CoreController state machine unit tests — F11: state transitions, error recovery."""

from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np
import pytest

from voiceime.protocols import AudioData, ASRResult, TrayCommand


@pytest.fixture
def qapp_fixture(qapp):
    return qapp


class TestCoreStateMachine:
    """CoreController state machine — transitions, error states, recovery."""

    def _make_core(self, state="READY"):
        """Create a CoreController with properly initialized QObject base."""
        from voiceime.core import CoreController

        core = CoreController.__new__(CoreController)
        # Manually init QObject to get signals working
        super(CoreController, core).__init__()
        core._state = state
        core._config = MagicMock()
        core._config.get = MagicMock(return_value=True)  # quick_mode=True
        core._recorder = MagicMock()
        core._asr = MagicMock()
        core._output = MagicMock()
        core._hotkey = None
        core._tray = None
        core._model_mgr = None
        core._settings_window = None
        core._inference_future = None
        core._current_audio = None
        core._hotkey_queue = MagicMock()
        core._cmd_queue = MagicMock()
        core._result_queue = MagicMock()
        # Init QTimers
        from PyQt6.QtCore import QTimer
        core._timer = QTimer()
        core._rec_timer = QTimer()
        return core

    def test_should_transition_to_recording_when_hotkey_down_from_ready(self, qapp_fixture):
        core = self._make_core(state="READY")
        core._on_hotkey_down()
        assert core._state == "RECORDING"

    def test_should_not_record_when_not_ready(self, qapp_fixture):
        for state in ("INFERRING", "OUTPUTTING", "CONFIRMING"):
            core = self._make_core(state=state)
            core._on_hotkey_down()
            assert core._state == state

    def test_should_not_record_when_paused(self, qapp_fixture):
        core = self._make_core(state="PAUSED")
        core._on_hotkey_down()
        assert core._state == "PAUSED"

    def test_should_enter_error_mic_when_recorder_fails(self, qapp_fixture):
        from voiceime.recorder.stream import DeviceDisconnectedError

        core = self._make_core(state="READY")
        core._recorder.start_recording.side_effect = DeviceDisconnectedError("mic gone")
        core._on_hotkey_down()
        assert core._state == "ERROR_MIC"

    def test_should_transition_to_inferring_when_recording_stops(self, qapp_fixture):
        core = self._make_core(state="RECORDING")
        pcm = np.ones(16000, dtype=np.float32)
        core._recorder.stop_recording.return_value = AudioData(
            pcm=pcm, duration_ms=1000, sample_rate=16000
        )
        core._asr.is_loaded = True
        core._asr._executor = MagicMock()
        core._on_hotkey_up()
        assert core._state == "INFERRING"

    def test_should_return_to_ready_when_audio_is_empty(self, qapp_fixture):
        core = self._make_core(state="RECORDING")
        core._recorder.stop_recording.return_value = AudioData(
            pcm=np.array([], dtype=np.float32), duration_ms=100, sample_rate=16000
        )
        core._on_hotkey_up()
        assert core._state == "READY"

    def test_should_enter_error_model_when_asr_not_loaded(self, qapp_fixture):
        core = self._make_core(state="RECORDING")
        pcm = np.ones(16000, dtype=np.float32)
        core._recorder.stop_recording.return_value = AudioData(
            pcm=pcm, duration_ms=1000, sample_rate=16000
        )
        core._asr.is_loaded = False
        core._on_hotkey_up()
        assert core._state == "ERROR_MODEL"

    def test_should_output_directly_in_quick_mode(self, qapp_fixture):
        core = self._make_core(state="READY")
        core._config.get = MagicMock(return_value=True)

        result = ASRResult(text="你好世界", language="zh", inference_ms=500, segments=[])
        core._on_inference_complete(result)

        core._output.output.assert_called_once_with("你好世界")

    def test_should_enter_confirming_in_non_quick_mode(self, qapp_fixture):
        core = self._make_core(state="READY")
        core._config.get = MagicMock(return_value=False)

        result = ASRResult(text="你好世界", language="zh", inference_ms=500, segments=[])
        core._on_inference_complete(result)
        assert core._state == "CONFIRMING"

    def test_should_return_to_ready_when_transcription_empty(self, qapp_fixture):
        core = self._make_core(state="READY")
        result = ASRResult(text="", language="", inference_ms=100, segments=[])
        core._on_inference_complete(result)
        assert core._state == "READY"

    def test_should_return_to_ready_after_output(self, qapp_fixture):
        core = self._make_core(state="READY")
        core._output.output.return_value = MagicMock(success=True)
        core._do_output("test")
        assert core._state == "READY"

    def test_should_handle_tray_pause_command(self, qapp_fixture):
        core = self._make_core(state="READY")
        core._handle_tray_command(TrayCommand(action="pause"))
        assert core._state == "PAUSED"

    def test_should_handle_tray_resume_command(self, qapp_fixture):
        core = self._make_core(state="PAUSED")
        core._handle_tray_command(TrayCommand(action="resume"))
        assert core._state == "READY"

    def test_should_not_resume_from_non_paused_state(self, qapp_fixture):
        core = self._make_core(state="RECORDING")
        core._handle_tray_command(TrayCommand(action="resume"))
        assert core._state == "RECORDING"
