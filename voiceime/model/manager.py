"""ModelManager — model download, verification, and lifecycle."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

from voiceime.model.downloader import DownloadError, download_model
from voiceime.protocols import DownloadProgress

logger = logging.getLogger("voiceime.model.manager")

_REQUIRED_FILES = ("model.bin", "config.json", "vocabulary.json")

# Default project-local model directory
_DEFAULT_PROJECT_MODEL_DIR = Path(__file__).resolve().parent


def _get_project_model_dir() -> Path | None:
    """Return project-local model dir, or None if disabled via env var.

    Set VOICEIME_LOCAL_MODEL_DIR="" to disable project-local lookup.
    """
    env = os.environ.get("VOICEIME_LOCAL_MODEL_DIR")
    if env is not None:
        return Path(env) if env else None
    return _DEFAULT_PROJECT_MODEL_DIR


class ModelManager:
    """Manages ASR model files on disk."""

    def __init__(self, models_dir: Path) -> None:
        self._models_dir = models_dir
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._progress: DownloadProgress | None = None

    def ensure_model(self, model_name: str, quantization: str = "int8") -> Path:
        """Ensure model files exist locally, downloading if necessary.

        Search order:
        1. Project-local voiceime/model/ (for development / portable use)
        2. APPDATA models_dir / model_name
        3. Download from HuggingFace
        """
        # 1. Check project-local model directory
        local_dir = _get_project_model_dir()
        if local_dir and self.verify_model(local_dir):
            logger.info("Model found in project directory: %s", local_dir)
            return local_dir

        # 2. Check APPDATA models directory
        target = self._models_dir / model_name
        if self.verify_model(target):
            logger.info("Model %s verified at %s", model_name, target)
            return target

        # 3. Download
        logger.info("Model %s not found, downloading...", model_name)
        return download_model(
            model_name=model_name,
            dest_dir=self._models_dir,
            quantization=quantization,
            progress_callback=self._on_progress,
        )

    def verify_model(self, model_dir: Path) -> bool:
        """Verify all required model files exist and are non-empty."""
        if not model_dir.exists():
            return False
        for fname in _REQUIRED_FILES:
            fpath = model_dir / fname
            if not fpath.exists() or fpath.stat().st_size == 0:
                return False
        return True

    @property
    def download_progress(self) -> DownloadProgress | None:
        return self._progress

    @property
    def available_models(self) -> list[str]:
        """List locally available model directories."""
        if not self._models_dir.exists():
            return []
        return [
            d.name
            for d in self._models_dir.iterdir()
            if d.is_dir() and self.verify_model(d)
        ]

    def _on_progress(self, downloaded: int, total: int, speed: float) -> None:
        eta = (total - downloaded) / speed if speed > 0 else 0
        self._progress = DownloadProgress(
            downloaded_bytes=downloaded,
            total_bytes=total,
            speed_bps=speed,
            eta_seconds=eta,
        )
