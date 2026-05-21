"""CoreController — global orchestrator and state machine for VoiceIME."""

from __future__ import annotations

import logging
import sys
from concurrent.futures import Future
from pathlib import Path
from queue import Queue

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from voiceime.asr.engine import (
    ASREngine,
    InferenceError,
    InferenceTimeoutError,
    ModelNotLoadedError,
)
from voiceime.config.manager import ConfigManager
from voiceime.hotkey.manager import HotkeyManager
from voiceime.model.manager import ModelManager
from voiceime.output.controller import OutputController
from voiceime.protocols import (
    ASRResult,
    AudioData,
    HotKeyEvent,
    OutputResult,
    TrayCommand,
)
from voiceime.recorder.stream import DeviceDisconnectedError, RecorderStream
from voiceime.ui.tray import SystemTray

logger = logging.getLogger("voiceime.core")

# ── State constants ──────────────────────────────────
UNINITIALIZED = "UNINITIALIZED"
READY = "READY"
RECORDING = "RECORDING"
INFERRING = "INFERRING"
CONFIRMING = "CONFIRMING"
OUTPUTTING = "OUTPUTTING"
PAUSED = "PAUSED"

ERROR_MIC = "ERROR_MIC"
ERROR_MODEL = "ERROR_MODEL"
ERROR_INFERENCE_TIMEOUT = "ERROR_INFERENCE_TIMEOUT"
ERROR_CLIPBOARD = "ERROR_CLIPBOARD"

_ERROR_STATES = {ERROR_MIC, ERROR_MODEL, ERROR_INFERENCE_TIMEOUT, ERROR_CLIPBOARD}


class CoreController(QObject):
    """Central orchestrator wiring all modules together."""

    # Signals for UI
    state_changed = pyqtSignal(str)
    recording_progress = pyqtSignal(int)  # duration_ms
    asr_result_received = pyqtSignal(object)  # ASRResult
    error_occurred = pyqtSignal(str, str)  # error_state, message

    def __init__(self, config: ConfigManager, model_mgr: ModelManager | None = None) -> None:
        super().__init__()
        self._config = config
        self._state = UNINITIALIZED

        # Queues for cross-thread communication
        self._hotkey_queue: Queue[HotKeyEvent] = Queue()
        self._cmd_queue: Queue[TrayCommand] = Queue()
        self._result_queue: Queue[ASRResult] = Queue()

        # Modules (initialized in initialize())
        self._hotkey: HotkeyManager | None = None
        self._recorder: RecorderStream | None = None
        self._asr: ASREngine | None = None
        self._output: OutputController | None = None
        self._model_mgr: ModelManager | None = model_mgr
        self._tray: SystemTray | None = None
        self._settings_window = None

        # ASR inference future
        self._inference_future: Future | None = None
        self._current_audio: AudioData | None = None

        # QTimer for polling queues
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_queues)

        # Recording progress timer
        self._rec_timer = QTimer(self)
        self._rec_timer.timeout.connect(self._update_recording_progress)

    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, state: str) -> None:
        if self._state != state:
            logger.info("State: %s → %s", self._state, state)
            self._state = state
            self.state_changed.emit(state)

    # ── Initialization ────────────────────────────────

    def initialize(self) -> bool:
        """Initialize all modules and transition to READY."""
        try:
            # Model manager (reuse from FirstRunWizard if provided)
            if self._model_mgr is None:
                models_dir = self._config.data_dir / "models"
                self._model_mgr = ModelManager(models_dir)

            # Hotkey manager
            hotkey_name = self._config.get("hotkey", "caps_lock")
            self._hotkey = HotkeyManager(hotkey_name)
            self._hotkey.set_callback(
                on_keydown=self._on_hotkey_down,
                on_keyup=self._on_hotkey_up,
            )
            self._hotkey_queue = self._hotkey.queue

            # Recorder
            self._recorder = RecorderStream(
                min_record_ms=self._config.get("ui.min_record_ms", 200),
                max_record_s=self._config.get("ui.max_record_s", 60),
            )

            # ASR engine
            self._asr = ASREngine()

            # Output controller
            self._output = OutputController(
                clipboard_delay_ms=self._config.get("ui.clipboard_restore_delay_ms", 50)
            )

            # System tray
            self._tray = SystemTray(self._cmd_queue)

            # Load model in background
            self._load_model_async()

            return True
        except Exception as exc:
            logger.error("Initialization failed: %s", exc)
            self.error_occurred.emit(ERROR_MODEL, str(exc))
            return False

    def _load_model_async(self) -> None:
        """Load ASR model in a background thread."""
        from concurrent.futures import ThreadPoolExecutor

        def _load():
            try:
                model_name = self._config.get("asr.model", "large-v3-turbo")
                quantization = self._config.get("asr.quantization", "int8")
                model_dir = self._model_mgr.ensure_model(model_name, quantization)
                self._asr.set_model_dir(model_dir)
                self._asr.load_model()
                self._set_state(READY)
                if self._tray:
                    self._tray.set_status("ready")
            except Exception as exc:
                logger.error("Model loading failed: %s", exc)
                self._set_state(ERROR_MODEL)
                self.error_occurred.emit(ERROR_MODEL, str(exc))
                if self._tray:
                    self._tray.set_status("error")

        self._set_state("LOADING")
        if self._tray:
            self._tray.set_status("loading")

        import threading
        threading.Thread(target=_load, daemon=True).start()

    # ── Lifecycle ─────────────────────────────────────

    def start(self) -> None:
        """Start all subsystems and begin polling."""
        if self._tray:
            self._tray.start()
        if self._hotkey:
            self._hotkey.start()
        self._timer.start(50)  # 50ms polling
        logger.info("CoreController started")

    def stop(self) -> None:
        """Stop all subsystems cleanly."""
        self._timer.stop()
        self._rec_timer.stop()
        if self._hotkey:
            self._hotkey.stop()
        if self._tray:
            self._tray.stop()
        if self._asr:
            self._asr.shutdown()
        logger.info("CoreController stopped")

    # ── Queue polling ─────────────────────────────────

    def _poll_queues(self) -> None:
        """Called every 50ms to drain all queues."""
        # Process hotkey events
        if self._hotkey:
            self._hotkey.process_pending_events()

        # Process tray commands
        while not self._cmd_queue.empty():
            try:
                cmd = self._cmd_queue.get_nowait()
                self._handle_tray_command(cmd)
            except Exception:
                break

        # Check ASR inference result
        if self._inference_future and self._inference_future.done():
            try:
                result = self._inference_future.result(timeout=0)
                self._on_inference_complete(result)
            except InferenceTimeoutError:
                self._set_state(ERROR_INFERENCE_TIMEOUT)
                self.error_occurred.emit(
                    ERROR_INFERENCE_TIMEOUT, "ASR inference timed out"
                )
            except Exception as exc:
                logger.error("Inference error: %s", exc)
                self._set_state(READY)
                self.error_occurred.emit(ERROR_MODEL, str(exc))
            finally:
                self._inference_future = None

    # ── Hotkey handlers ───────────────────────────────

    def _on_hotkey_down(self) -> None:
        if self._state not in (READY,):
            return
        try:
            if self._recorder:
                self._recorder.start_recording()
                self._set_state(RECORDING)
                self._rec_timer.start(100)
                if self._tray:
                    self._tray.set_status("recording")
        except DeviceDisconnectedError as exc:
            self._set_state(ERROR_MIC)
            self.error_occurred.emit(ERROR_MIC, str(exc))
        except Exception as exc:
            logger.error("Failed to start recording: %s", exc)

    def _on_hotkey_up(self) -> None:
        if self._state != RECORDING:
            return
        self._rec_timer.stop()
        try:
            audio_data = self._recorder.stop_recording() if self._recorder else AudioData(
                pcm=__import__("numpy").array([]), duration_ms=0, sample_rate=16000
            )

            if len(audio_data.pcm) == 0:
                logger.debug("No audio captured (too short or empty)")
                self._set_state(READY)
                if self._tray:
                    self._tray.set_status("ready")
                return

            self._current_audio = audio_data
            self._start_inference(audio_data)

        except DeviceDisconnectedError as exc:
            self._set_state(ERROR_MIC)
            self.error_occurred.emit(ERROR_MIC, str(exc))
        except Exception as exc:
            logger.error("Failed to stop recording: %s", exc)
            self._set_state(READY)

    def _update_recording_progress(self) -> None:
        if self._recorder and self._recorder.is_recording:
            self.recording_progress.emit(self._recorder.duration_ms)

    # ── ASR inference ─────────────────────────────────

    def _start_inference(self, audio_data: AudioData) -> None:
        """Submit ASR inference to background thread."""
        if not self._asr or not self._asr.is_loaded:
            self._set_state(ERROR_MODEL)
            self.error_occurred.emit(ERROR_MODEL, "Model not loaded")
            return

        self._set_state(INFERRING)
        if self._tray:
            self._tray.set_status("loading")

        from concurrent.futures import ThreadPoolExecutor

        language = self._config.get("asr.language", "auto")
        vad_filter = self._config.get("asr.vad_filter", True)
        beam_size = self._config.get("asr.beam_size", 5)

        self._inference_future = self._asr._executor.submit(
            self._asr.transcribe,
            audio_data.pcm,
            language=language,
            vad_filter=vad_filter,
            beam_size=beam_size,
        )

    def _on_inference_complete(self, result: ASRResult) -> None:
        """Handle completed ASR inference."""
        self.asr_result_received.emit(result)

        if not result.text:
            logger.info("Empty transcription result")
            self._set_state(READY)
            if self._tray:
                self._tray.set_status("ready")
            return

        # Quick mode: skip confirming, output directly
        quick_mode = self._config.get("ui.quick_mode", True)
        if quick_mode:
            self._do_output(result.text)
        else:
            self._set_state(CONFIRMING)

    # ── Text output ───────────────────────────────────

    def _do_output(self, text: str) -> None:
        """Execute text output to focused window."""
        self._set_state(OUTPUTTING)
        try:
            if self._output:
                result = self._output.output(text)
                if not result.success:
                    logger.error("Output failed: %s", result.error)
                    self.error_occurred.emit(ERROR_CLIPBOARD, result.error or "Output failed")
        except Exception as exc:
            logger.error("Output error: %s", exc)
        finally:
            self._set_state(READY)
            if self._tray:
                self._tray.set_status("ready")

    # ── Tray command handling ─────────────────────────

    def _handle_tray_command(self, cmd: TrayCommand) -> None:
        action = cmd.action
        if action == "exit":
            logger.info("Exit requested from tray")
            self.stop()
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()
        elif action == "pause":
            self._set_state(PAUSED)
            if self._tray:
                self._tray.set_status("paused")
        elif action == "resume":
            if self._state == PAUSED:
                self._set_state(READY)
                if self._tray:
                    self._tray.set_status("ready")
        elif action == "settings":
            self._open_settings()

    # ── Settings window ────────────────────────────────

    def _open_settings(self) -> None:
        """Open or focus the settings window."""
        if self._settings_window is not None:
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            return
        from voiceime.ui.settings import SettingsWindow

        self._settings_window = SettingsWindow(self._config, self._model_mgr)
        self._settings_window.destroyed.connect(self._on_settings_closed)
        self._settings_window.show()

    def _on_settings_closed(self) -> None:
        self._settings_window = None
