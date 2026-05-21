"""ASREngine — faster-whisper model loading and transcription."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue

import numpy as np

from voiceime.protocols import ASRResult

logger = logging.getLogger("voiceime.asr.engine")

_INFERENCE_TIMEOUT_S = 30


class ModelNotLoadedError(Exception):
    pass


class InferenceTimeoutError(Exception):
    pass


class InferenceError(Exception):
    pass


class ASREngine:
    """Wraps faster-whisper for speech-to-text inference."""

    def __init__(self, model_dir: Path | None = None) -> None:
        self._model_dir = model_dir
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._result_queue: Queue[ASRResult] = Queue()
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def result_queue(self) -> Queue[ASRResult]:
        return self._result_queue

    def set_model_dir(self, model_dir: Path) -> None:
        self._model_dir = model_dir

    def load_model(self, cpu_threads: int = 4) -> None:
        """Load faster-whisper model. Call from worker thread — blocks during load."""
        if self._loaded:
            return

        if self._model_dir is None or not self._model_dir.exists():
            raise ModelNotLoadedError(f"Model directory not found: {self._model_dir}")

        logger.info("Loading model from %s ...", self._model_dir)
        start = time.monotonic()

        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                str(self._model_dir),
                device="cpu",
                compute_type="int8",
                cpu_threads=cpu_threads,
            )
            elapsed = time.monotonic() - start
            self._loaded = True
            logger.info("Model loaded in %.1fs", elapsed)
        except Exception as exc:
            self._model = None
            raise ModelNotLoadedError(f"Failed to load model: {exc}") from exc

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = None,
        vad_filter: bool = True,
        beam_size: int = 5,
    ) -> ASRResult:
        """Run ASR inference on audio data. Runs synchronously in caller's thread."""
        if not self._loaded or self._model is None:
            raise ModelNotLoadedError("Model not loaded")

        if len(audio) == 0:
            return ASRResult(text="", language="", inference_ms=0, segments=[])

        logger.info("Transcribing %d samples ...", len(audio))

        try:
            return self._do_transcribe(audio, language, vad_filter, beam_size)
        except Exception as exc:
            raise InferenceError(f"Inference failed: {exc}") from exc

    def _do_transcribe(
        self,
        audio: np.ndarray,
        language: str | None,
        vad_filter: bool,
        beam_size: int,
    ) -> ASRResult:
        start = time.monotonic()

        segments_iter, info = self._model.transcribe(
            audio,
            language=language if language and language != "auto" else None,
            vad_filter=vad_filter,
            beam_size=beam_size,
        )

        segments = []
        text_parts = []
        for seg in segments_iter:
            segments.append(
                {"start": seg.start, "end": seg.end, "text": seg.text}
            )
            text_parts.append(seg.text)

        text = "".join(text_parts).strip()
        elapsed_ms = int((time.monotonic() - start) * 1000)

        detected_lang = info.language if hasattr(info, "language") else ""
        logger.info(
            "Transcribed: lang=%s, %dms, %d chars",
            detected_lang,
            elapsed_ms,
            len(text),
        )

        return ASRResult(
            text=text,
            language=detected_lang,
            inference_ms=elapsed_ms,
            segments=segments,
        )

    def unload_model(self) -> None:
        """Release model from memory."""
        if self._model is not None:
            del self._model
            self._model = None
        self._loaded = False
        logger.info("Model unloaded")

    def shutdown(self) -> None:
        """Shutdown executor."""
        self.unload_model()
        self._executor.shutdown(wait=False)
