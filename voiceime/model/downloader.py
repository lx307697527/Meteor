"""HuggingFace model downloader with resume support."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Callable

logger = logging.getLogger("voiceime.model.downloader")

_HF_BASE = "https://huggingface.co"
_MAX_RETRIES = 3

# Known CTranslate2 model repos
_MODEL_REPOS: dict[str, str] = {
    "large-v3-turbo": "Systran/faster-whisper-large-v3",
    "large-v3": "Systran/faster-whisper-large-v3",
    "medium": "Systran/faster-whisper-medium",
    "small": "Systran/faster-whisper-small",
    "base": "Systran/faster-whisper-base",
    "tiny": "Systran/faster-whisper-tiny",
}

_REQUIRED_FILES = ("model.bin", "config.json", "vocabulary.txt")


class DownloadError(Exception):
    pass


def resolve_repo(model_name: str) -> str:
    """Return HuggingFace repo ID for a model name."""
    repo = _MODEL_REPOS.get(model_name)
    if not repo:
        raise DownloadError(f"Unknown model: {model_name}")
    return repo


def download_model(
    model_name: str,
    dest_dir: Path,
    quantization: str = "int8",
    progress_callback: Callable | None = None,
) -> Path:
    """Download a faster-whisper model from HuggingFace.

    Uses huggingface_hub library for resume support.
    Returns the local model directory path.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise DownloadError(
            "huggingface_hub not installed. Run: pip install huggingface_hub"
        )

    repo_id = resolve_repo(model_name)
    target = dest_dir / model_name

    if target.exists() and _verify_files(target):
        logger.info("Model %s already exists at %s", model_name, target)
        return target

    logger.info("Downloading model %s from %s ...", model_name, repo_id)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            local_dir = snapshot_download(
                repo_id=repo_id,
                local_dir=str(target),
                resume_download=True,
            )
            logger.info("Model %s downloaded to %s", model_name, local_dir)
            return Path(local_dir)
        except Exception as exc:
            logger.warning(
                "Download attempt %d/%d failed: %s", attempt, _MAX_RETRIES, exc
            )
            if attempt == _MAX_RETRIES:
                raise DownloadError(
                    f"Failed to download {model_name} after {_MAX_RETRIES} attempts: {exc}"
                ) from exc

    raise DownloadError("Unreachable")


def _verify_files(model_dir: Path) -> bool:
    """Check that all required model files exist."""
    return all((model_dir / f).exists() for f in _REQUIRED_FILES)
