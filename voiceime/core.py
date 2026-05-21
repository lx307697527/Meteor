"""CoreController — global orchestrator and state machine for VoiceIME."""

from __future__ import annotations

import logging
import time
import sys
from concurrent.futures import Future
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal

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
from voiceime.postprocess.pipeline import PostProcessPipeline
from voiceime.protocols import (
    ASRResult,
    AudioData,
    ContextOverrides,
    HotKeyEvent,
    HistoryRecord,
    OutputResult,
    ProcessContext,
    ProcessResult,
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
ERROR_LLM_TIMEOUT = "ERROR_LLM_TIMEOUT"
ERROR_CLIPBOARD = "ERROR_CLIPBOARD"

_ERROR_STATES = {ERROR_MIC, ERROR_MODEL, ERROR_INFERENCE_TIMEOUT, ERROR_LLM_TIMEOUT, ERROR_CLIPBOARD}

# Inference timeout in seconds (polled every 50ms)
_INFERENCE_TIMEOUT_S = 30


class CoreController(QObject):
    """Central orchestrator wiring all modules together."""

    # Signals for UI
    state_changed = pyqtSignal(str)
    recording_progress = pyqtSignal(int, list)  # duration_ms, waveform levels
    asr_result_received = pyqtSignal(object)  # ASRResult
    llm_result_received = pyqtSignal(object)  # LLMResult / ProcessResult
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
        self._pipeline: PostProcessPipeline | None = None
        self._history = None
        self._hotword_repo = None
        self._llm_client = None
        self._keyring_store = None
        self._floating_bar = None
        self._settings_window = None
        self._history_window = None
        self._hotword_window = None
        self._context_engine = None
        self._current_overrides: ContextOverrides | None = None

        # ASR inference future
        self._inference_future: Future | None = None
        self._inference_start_time: float = 0.0
        self._current_audio: AudioData | None = None
        self._last_raw_text: str = ""
        self._last_processed_text: str = ""
        self._last_asr_result: ASRResult | None = None

        # LLM polish future
        self._polish_future: Future | None = None

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
            self._update_floating_bar()

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

            # Phase 2: KeyringStore
            from voiceime.keyring.store import KeyringStore
            self._keyring_store = KeyringStore()

            # Phase 2: HotwordRepo
            from voiceime.hotword.repository import HotwordRepo
            self._hotword_repo = HotwordRepo()

            # Phase 2: HistoryRepo
            from voiceime.history.repository import HistoryRepo
            self._history = HistoryRepo()

            # Phase 2: LLM Client
            from voiceime.llm.client import LLMClient
            self._llm_client = LLMClient(self._config, self._keyring_store)

            # Phase 2: PostProcessPipeline
            self._pipeline = PostProcessPipeline(
                config=self._config,
                hotword_provider=self._hotword_repo,
                llm_provider=self._llm_client,
            )

            # Phase 3: ContextEngine
            from voiceime.context.engine import ContextEngine
            self._context_engine = ContextEngine(config=self._config)

            # System tray
            self._tray = SystemTray(self._cmd_queue)

            # Phase 2: FloatingBar
            from voiceime.ui.floating import FloatingBar
            self._floating_bar = FloatingBar()
            self._wire_floating_bar()

            # Load model in background
            self._load_model_async()

            return True
        except Exception as exc:
            logger.error("Initialization failed: %s", exc)
            self.error_occurred.emit(ERROR_MODEL, str(exc))
            return False

    def _wire_floating_bar(self) -> None:
        """Connect FloatingBar signals and CoreController signals."""
        if not self._floating_bar:
            return
        self.state_changed.connect(self._on_state_changed_for_floating)
        self.recording_progress.connect(self._floating_bar.on_recording_progress)
        self.asr_result_received.connect(self._on_asr_for_floating)
        self._floating_bar.output_requested.connect(self._on_floating_output)
        self._floating_bar.polish_requested.connect(self._do_polish)
        self._floating_bar.rerecord_requested.connect(self._on_floating_rerecord)
        self._floating_bar.cancel_requested.connect(self._on_floating_cancel)

    def _on_state_changed_for_floating(self, state: str) -> None:
        if not self._floating_bar:
            return
        if state == RECORDING:
            self._floating_bar.show_recording()
        elif state == INFERRING:
            self._floating_bar.show_inferring()
        elif state == CONFIRMING:
            self._floating_bar.show_confirming(
                self._last_processed_text,
                language=self._last_asr_result.language if self._last_asr_result else "",
                inference_ms=self._last_asr_result.inference_ms if self._last_asr_result else 0,
            )
        elif state in (READY, OUTPUTTING, PAUSED) or state in _ERROR_STATES:
            self._floating_bar.hide_bar()

    def _on_asr_for_floating(self, result: ASRResult) -> None:
        if self._state == INFERRING and self._floating_bar:
            self._floating_bar.show_inferring()

    def _update_floating_bar(self) -> None:
        """Update floating bar based on current state (called from _set_state)."""
        pass  # Handled by _on_state_changed_for_floating

    def _on_floating_output(self) -> None:
        self._do_output(self._last_processed_text)

    def _on_floating_rerecord(self) -> None:
        self._set_state(READY)
        self._on_hotkey_down()

    def _on_floating_cancel(self) -> None:
        self._set_state(READY)
        if self._tray:
            self._tray.set_status("ready")

    def _load_model_async(self) -> None:
        """Load ASR model in a background thread."""
        from concurrent.futures import ThreadPoolExecutor

        def _load():
            try:
                model_name = self._config.get("asr.model", "large-v3-turbo")
                quantization = self._config.get("asr.quantization", "int8")
                self._asr.unload_model()
                model_dir = self._model_mgr.ensure_model(model_name, quantization)
                self._asr.set_model_dir(model_dir)
                cpu_threads = self._config.get("asr.cpu_threads", 4)
                self._asr.load_model(cpu_threads=cpu_threads)
                # Phase 2: VirtualLock model memory if enabled
                self._try_lock_model_memory()
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

    def _try_lock_model_memory(self) -> None:
        """Attempt to lock ASR model memory via VirtualLock if configured."""
        if not self._config.get("ui.memory_lock", False):
            return
        try:
            from voiceime.asr.memory import lock_model_memory, start_heartbeat
            model = getattr(self._asr, "_model", None)
            if model is None:
                logger.debug("No model object available for memory locking")
                return
            # Get model buffer info — ctranslate2 models store weights in numpy arrays
            import sys
            total_size = 0
            base_ptr = None
            for attr_name in dir(model):
                try:
                    attr = getattr(model, attr_name)
                    import numpy as np
                    if isinstance(attr, np.ndarray) and attr.nbytes > 0:
                        if base_ptr is None:
                            base_ptr = attr.__array_interface__["data"][0]
                        total_size += attr.nbytes
                except Exception:
                    continue
            if total_size > 0 and base_ptr is not None:
                limit_gb = self._config.get("ui.memory_lock_limit_gb", 3.5)
                lock_model_memory(base_ptr, total_size, limit_gb)
                start_heartbeat()
        except Exception as exc:
            logger.warning("Memory locking failed (non-fatal): %s", exc)

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
        # Phase 2: unlock memory and stop heartbeat
        try:
            from voiceime.asr.memory import stop_heartbeat, get_stats
            stop_heartbeat()
            stats = get_stats()
            if stats.locked_bytes > 0:
                logger.info("Releasing %d locked memory regions on shutdown", stats.locked_regions)
        except Exception:
            pass
        if self._asr:
            self._asr.shutdown()
        if self._llm_client:
            self._llm_client.shutdown()
        if self._history:
            self._history.close()
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
            except Exception as exc:
                logger.error("Tray command error: %s", exc)
                break

        # Check ASR inference result
        if self._inference_future:
            if self._inference_future.done():
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
                    self._inference_start_time = 0.0
            elif self._inference_start_time > 0:
                elapsed = time.monotonic() - self._inference_start_time
                if elapsed > _INFERENCE_TIMEOUT_S:
                    logger.warning(
                        "Inference timed out after %ds, cancelling", _INFERENCE_TIMEOUT_S
                    )
                    self._inference_future.cancel()
                    self._inference_future = None
                    self._inference_start_time = 0.0
                    self._set_state(ERROR_INFERENCE_TIMEOUT)
                    self.error_occurred.emit(
                        ERROR_INFERENCE_TIMEOUT, "ASR inference timed out"
                    )

        # Check LLM polish result
        if self._polish_future and self._polish_future.done():
            try:
                result = self._polish_future.result(timeout=0)
                self._on_polish_complete(result)
            except Exception as exc:
                logger.error("Polish error: %s", exc)
                self._on_polish_complete(
                    ProcessResult(text=self._last_processed_text, is_polished=False, steps_applied=[])
                )
            finally:
                self._polish_future = None

    # ── Hotkey handlers ───────────────────────────────

    def _on_hotkey_down(self) -> None:
        if self._state in _ERROR_STATES:
            self._set_state(READY)
            if self._tray:
                self._tray.set_status("ready")
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
            levels = self._recorder.current_levels
            self.recording_progress.emit(self._recorder.duration_ms, levels)

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

        language = self._config.get("asr.language", "auto")
        vad_filter = self._config.get("asr.vad_filter", True)
        beam_size = self._config.get("asr.beam_size", 5)

        self._inference_start_time = time.monotonic()
        self._inference_future = self._asr._executor.submit(
            self._asr.transcribe,
            audio_data.pcm,
            language=language,
            vad_filter=vad_filter,
            beam_size=beam_size,
        )

    def _on_inference_complete(self, result: ASRResult) -> None:
        """Handle completed ASR inference — run postprocess then confirm/output."""
        self.asr_result_received.emit(result)
        self._last_asr_result = result
        self._last_raw_text = result.text

        if not result.text:
            logger.info("Empty transcription result")
            self._set_state(READY)
            if self._tray:
                self._tray.set_status("ready")
            return

        # Phase 3: Context-aware overrides
        context: ProcessContext | None = None
        self._current_overrides = None
        ctx_engine = getattr(self, '_context_engine', None)
        if ctx_engine:
            context = ctx_engine.get_context()
            self._current_overrides = ctx_engine.match_rules(context)
            if self._current_overrides:
                logger.debug(
                    "Context override matched: quick_mode=%s, polish_mode=%s",
                    self._current_overrides.quick_mode,
                    self._current_overrides.polish_mode,
                )

        # Run postprocess pipeline with context
        if self._pipeline:
            processed = self._pipeline.process(result.text, context=context)
            self._last_processed_text = processed.text
        else:
            self._last_processed_text = result.text

        # Determine quick_mode: context override takes priority over global config
        if self._current_overrides and self._current_overrides.quick_mode is not None:
            quick_mode = self._current_overrides.quick_mode
        else:
            quick_mode = self._config.get("ui.quick_mode", True)

        # Auto-polish via context override
        if (self._current_overrides
                and self._current_overrides.polish_mode == "auto"
                and self._pipeline and self._llm_client and self._llm_client.is_configured):
            self._do_polish()

        if quick_mode:
            self._do_output(self._last_processed_text)
        else:
            self._set_state(CONFIRMING)

    # ── LLM polish ────────────────────────────────────

    def _do_polish(self) -> None:
        """Polish current text via LLM."""
        if not self._pipeline or not self._last_processed_text:
            return
        # Use context-specific system prompt if available
        prompt = None
        overrides = getattr(self, '_current_overrides', None)
        if overrides and overrides.system_prompt:
            prompt = overrides.system_prompt
        from concurrent.futures import ThreadPoolExecutor
        self._polish_future = self._pipeline._llm._executor.submit(
            self._pipeline.polish_only, self._last_processed_text, None, prompt
        )

    def _on_polish_complete(self, result: ProcessResult) -> None:
        """Handle completed LLM polish."""
        self.llm_result_received.emit(result)
        if result.is_polished:
            self._last_processed_text = result.text
        # Update confirming bar with polished text
        if self._state == CONFIRMING and self._floating_bar:
            self._floating_bar.show_confirming(
                self._last_processed_text,
                language=self._last_asr_result.language if self._last_asr_result else "",
                inference_ms=self._last_asr_result.inference_ms if self._last_asr_result else 0,
            )

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
            # Save to history
            self._save_history(text)
            self._set_state(READY)
            if self._tray:
                self._tray.set_status("ready")

    def _save_history(self, text: str) -> None:
        """Save recognition result to history."""
        if not self._history or not text:
            return
        try:
            # Phase 3: include context info in history
            app_name = None
            app_title = None
            ctx_engine = getattr(self, '_context_engine', None)
            if ctx_engine:
                ctx = ctx_engine.get_context()
                app_name = ctx.app_name
                app_title = ctx.app_title
            record = HistoryRecord(
                text=text,
                raw_text=self._last_raw_text or None,
                language=self._last_asr_result.language if self._last_asr_result else None,
                app_name=app_name,
                app_title=app_title,
                audio_duration_ms=self._current_audio.duration_ms if self._current_audio else None,
                inference_time_ms=self._last_asr_result.inference_ms if self._last_asr_result else None,
                is_polished=text != (self._last_raw_text or ""),
            )
            self._history.save(record)
        except Exception as exc:
            logger.warning("Failed to save history: %s", exc)

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
        elif action == "history":
            self._open_history()
        elif action == "hotword":
            self._open_hotword()

    # ── Settings window ────────────────────────────────

    def _open_settings(self) -> None:
        """Open or focus the settings window."""
        if self._settings_window is not None:
            self._settings_window.show()
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            return
        from voiceime.ui.settings import SettingsWindow

        self._settings_window = SettingsWindow(self._config, self._model_mgr, self._keyring_store)
        self._settings_window.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose
        )
        self._settings_window.accepted.connect(self._on_settings_closed)
        self._settings_window.destroyed.connect(self._on_settings_destroyed)
        self._settings_window.show()

    def _on_settings_closed(self) -> None:
        """Reload affected modules when settings are accepted."""
        # Reload hotkey if changed
        new_hotkey = self._config.get("hotkey", "caps_lock")
        if self._hotkey and self._hotkey.current_hotkey != new_hotkey:
            logger.info("Hotkey changed to %s, reloading...", new_hotkey)
            self._hotkey.stop()
            self._hotkey = HotkeyManager(new_hotkey)
            self._hotkey.set_callback(
                on_keydown=self._on_hotkey_down,
                on_keyup=self._on_hotkey_up,
            )
            self._hotkey_queue = self._hotkey.queue
            self._hotkey.start()
            logger.info("Hotkey reloaded to %s", new_hotkey)

        # Reload model if model name or cpu_threads changed
        if self._asr and self._asr.is_loaded:
            cur_name = self._config.get("asr.model", "large-v3-turbo")
            expected_dir = self._model_mgr._models_dir / cur_name if self._model_mgr else None
            if expected_dir and self._asr._model_dir != expected_dir:
                logger.info("Model changed to %s, reloading...", cur_name)
                self._load_model_async()

    def _on_settings_destroyed(self) -> None:
        """Cleanup settings window reference."""
        self._settings_window = None

    # ── History window ─────────────────────────────────

    def _open_history(self) -> None:
        """Open or focus the history window."""
        if self._history_window is not None:
            self._history_window.raise_()
            self._history_window.activateWindow()
            return
        from voiceime.ui.history_window import HistoryWindow

        self._history_window = HistoryWindow(self._history)
        self._history_window.re_output_requested.connect(self._do_output)
        self._history_window.destroyed.connect(self._on_history_closed)
        self._history_window.show()

    def _on_history_closed(self) -> None:
        self._history_window = None

    # ── Hotword window ─────────────────────────────────

    def _open_hotword(self) -> None:
        """Open or focus the hotword management window."""
        if self._hotword_window is not None:
            self._hotword_window.raise_()
            self._hotword_window.activateWindow()
            return
        from voiceime.ui.hotword_window import HotwordWindow

        self._hotword_window = HotwordWindow(self._hotword_repo)
        self._hotword_window.destroyed.connect(self._on_hotword_closed)
        self._hotword_window.show()

    def _on_hotword_closed(self) -> None:
        self._hotword_window = None
