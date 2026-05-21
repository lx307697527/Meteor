"""Full pipeline integration test — hotkey → recording → ASR → output."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voiceime.protocols import ASRResult, AudioData


@pytest.fixture
def qapp_fixture(qapp):
    return qapp


class TestPipelineE2E:
    """Integration: hotkey → recorder → ASR → output full chain (mocked externals)."""

    def _make_core(self, tmp_data_dir):
        """Create a CoreController with properly initialized QObject."""
        from voiceime.core import CoreController
        from voiceime.config.manager import ConfigManager

        config_file = tmp_data_dir / "config.json"
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        with (
            patch("voiceime.config.manager.config_path", return_value=config_file),
            patch("voiceime.config.manager.data_dir", return_value=tmp_data_dir),
        ):
            config = ConfigManager()

        core = CoreController.__new__(CoreController)
        super(CoreController, core).__init__()
        core._state = "READY"
        core._config = config
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
        from PyQt6.QtCore import QTimer
        core._timer = QTimer()
        core._rec_timer = QTimer()
        return core

    def test_should_complete_full_pipeline(self, tmp_data_dir, qapp_fixture):
        """Happy Path: keydown → recording → keyup → ASR → output → READY."""
        core = self._make_core(tmp_data_dir)

        pcm = np.ones(80000, dtype=np.float32)
        core._recorder.stop_recording.return_value = AudioData(
            pcm=pcm, duration_ms=5000, sample_rate=16000
        )
        core._asr.is_loaded = True
        core._asr._executor = MagicMock()
        core._output.output.return_value = MagicMock(success=True, method="clipboard", error=None)

        core._on_hotkey_down()
        assert core._state == "RECORDING"

        core._on_hotkey_up()
        assert core._state == "INFERRING"

        result = ASRResult(text="你好世界", language="zh", inference_ms=1500, segments=[])
        core._on_inference_complete(result)

        assert core._state == "READY"
        core._output.output.assert_called_once_with("你好世界")

    def test_should_handle_empty_asr_result(self, tmp_data_dir, qapp_fixture):
        """ASR returns empty text → back to READY, no output."""
        core = self._make_core(tmp_data_dir)

        result = ASRResult(text="", language="", inference_ms=100, segments=[])
        core._on_inference_complete(result)

        assert core._state == "READY"
        core._output.output.assert_not_called()

    def test_should_handle_output_failure_gracefully(self, tmp_data_dir, qapp_fixture):
        """Output fails → still returns to READY."""
        core = self._make_core(tmp_data_dir)
        core._output.output.return_value = MagicMock(success=False, method="", error="fail")

        result = ASRResult(text="test", language="zh", inference_ms=100, segments=[])
        core._on_inference_complete(result)

        assert core._state == "READY"

    def test_should_not_output_when_asr_not_loaded(self, tmp_data_dir, qapp_fixture):
        """ASR not loaded → ERROR_MODEL, no output attempted."""
        core = self._make_core(tmp_data_dir)
        pcm = np.ones(16000, dtype=np.float32)
        core._recorder.stop_recording.return_value = AudioData(
            pcm=pcm, duration_ms=1000, sample_rate=16000
        )
        core._asr.is_loaded = False

        core._on_hotkey_down()
        core._on_hotkey_up()

        assert core._state == "ERROR_MODEL"
        core._output.output.assert_not_called()
