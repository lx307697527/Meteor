"""Recorder — sounddevice InputStream with ring buffer."""

from __future__ import annotations

import logging
import threading
import time

import numpy as np
import sounddevice as sd

from voiceime.protocols import AudioData, DeviceInfo
from voiceime.recorder.device import get_default_device_id, list_devices

logger = logging.getLogger("voiceime.recorder.stream")

_SAMPLE_RATE = 16000
_CHANNELS = 1
_DTYPE = "float32"


class DeviceNotFoundError(Exception):
    pass


class DeviceDisconnectedError(Exception):
    pass


class RecorderStream:
    """Records 16kHz Mono PCM audio via sounddevice."""

    def __init__(
        self,
        min_record_ms: int = 200,
        max_record_s: int = 60,
        device_id: int | None = None,
    ) -> None:
        self._min_record_ms = min_record_ms
        self._max_record_s = max_record_s
        self._device_id = device_id
        self._stream: sd.InputStream | None = None
        self._buffer: list[np.ndarray] = []
        self._start_time: float = 0
        self._recording = False
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def duration_ms(self) -> int:
        if not self._recording:
            return 0
        return int((time.monotonic() - self._start_time) * 1000)

    @property
    def devices(self) -> list[DeviceInfo]:
        return list_devices()

    def start_recording(self) -> None:
        """Start recording audio."""
        with self._lock:
            if self._recording:
                return

            device_id = self._device_id or get_default_device_id()
            if device_id is None:
                raise DeviceNotFoundError("No microphone available")

            self._buffer = []
            self._start_time = time.monotonic()
            self._recording = True

            self._stream = sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
                device=device_id,
                callback=self._audio_callback,
                blocksize=_SAMPLE_RATE // 10,  # 100ms blocks
            )
            self._stream.start()
            logger.info("Recording started (device=%s)", device_id)

            # Spawn watchdog for max duration
            threading.Thread(
                target=self._max_duration_watchdog, daemon=True
            ).start()

    def stop_recording(self) -> AudioData:
        """Stop recording and return captured PCM data."""
        with self._lock:
            if not self._recording:
                return AudioData(
                    pcm=np.array([], dtype=np.float32), duration_ms=0, sample_rate=_SAMPLE_RATE
                )

            self._recording = False

            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as exc:
                    logger.warning("Error closing stream: %s", exc)
                self._stream = None

            duration_ms = int((time.monotonic() - self._start_time) * 1000)

            if not self._buffer:
                logger.debug("No audio data captured")
                return AudioData(
                    pcm=np.array([], dtype=np.float32),
                    duration_ms=duration_ms,
                    sample_rate=_SAMPLE_RATE,
                )

            pcm = np.concatenate(self._buffer).flatten()

            # Discard if too short (misfire)
            if duration_ms < self._min_record_ms:
                logger.debug(
                    "Recording too short (%dms < %dms), discarding",
                    duration_ms,
                    self._min_record_ms,
                )
                return AudioData(
                    pcm=np.array([], dtype=np.float32),
                    duration_ms=duration_ms,
                    sample_rate=_SAMPLE_RATE,
                )

            logger.info("Recording stopped, %dms, %d samples", duration_ms, len(pcm))
            return AudioData(pcm=pcm, duration_ms=duration_ms, sample_rate=_SAMPLE_RATE)

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """sounddevice callback — writes to ring buffer, zero-blocking."""
        if status:
            logger.warning("Audio callback status: %s", status)
        self._buffer.append(indata.copy())

    def _max_duration_watchdog(self) -> None:
        """Auto-stop recording when max duration is reached."""
        limit = self._max_record_s
        while self._recording:
            elapsed = time.monotonic() - self._start_time
            if elapsed >= limit:
                logger.info("Max recording time (%ds) reached, auto-stopping", limit)
                self.stop_recording()
                return
            time.sleep(0.5)
