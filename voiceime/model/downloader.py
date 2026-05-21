"""HuggingFace model downloader with resume support and mirror fallback."""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Callable

logger = logging.getLogger("voiceime.model.downloader")

_HF_BASE = "https://huggingface.co"
_HF_MIRROR = "https://hf-mirror.com"
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

_REQUIRED_FILES = ("model.bin", "config.json", "vocabulary.json")


class DownloadError(Exception):
    pass


def resolve_repo(model_name: str) -> str:
    """Return HuggingFace repo ID for a model name."""
    repo = _MODEL_REPOS.get(model_name)
    if not repo:
        raise DownloadError(f"Unknown model: {model_name}")
    return repo


def _resolve_endpoints() -> list[str]:
    """Return prioritized list of HF endpoints to try.

    Priority: HF_ENDPOINT env var → hf-mirror.com (primary for CN) → huggingface.co
    """
    env = os.environ.get("HF_ENDPOINT")
    if env:
        return [env, _HF_MIRROR, _HF_BASE]
    return [_HF_MIRROR, _HF_BASE]


def _get_total_size(endpoint: str, repo_id: str) -> int:
    """Return total downloadable bytes for a repo, or 0 on failure."""
    try:
        from huggingface_hub import HfApi

        api = HfApi(endpoint=endpoint)
        info = api.model_info(repo_id)
        return sum(
            s.size or 0
            for s in info.siblings
            if s.size and not s.rfilename.startswith(".")
        )
    except Exception:
        return 0


def _count_dir_bytes(directory: Path) -> int:
    """Recursively sum file sizes in a directory."""
    if not directory.exists():
        return 0
    total = 0
    try:
        for f in directory.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total


def _monitor_progress(
    target_dir: Path,
    total_size: int,
    callback: Callable | None,
    stop_event: threading.Event,
) -> None:
    """Background thread: poll target dir size and report progress."""
    while not stop_event.wait(1.0):
        downloaded = _count_dir_bytes(target_dir)
        if callback and total_size > 0:
            callback(min(downloaded, total_size), total_size, 0)


def _verify_files(model_dir: Path) -> bool:
    """Check that all required model files exist."""
    return all((model_dir / f).exists() for f in _REQUIRED_FILES)


def download_model(
    model_name: str,
    dest_dir: Path,
    quantization: str = "int8",
    progress_callback: Callable | None = None,
) -> Path:
    """Download a faster-whisper model from HuggingFace with mirror fallback.

    Tries endpoints in priority order (env var → huggingface.co → hf-mirror.com).
    Uses snapshot_download for reliable parallel downloads and caching.
    Reports per-file progress via the callback.
    Returns the local model directory path.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise DownloadError(
            "huggingface_hub 未安装，请运行: pip install huggingface_hub"
        )

    repo_id = resolve_repo(model_name)
    target = dest_dir / model_name

    if target.exists() and _verify_files(target):
        logger.info("Model %s already exists at %s", model_name, target)
        return target

    endpoints = _resolve_endpoints()
    last_error = None

    for endpoint in endpoints:
        logger.info("Downloading %s from %s ...", model_name, endpoint)

        total_size = _get_total_size(endpoint, repo_id)
        if total_size > 0:
            logger.info("Total download size: %.1f GB", total_size / (1024**3))

        stop_monitor = threading.Event()
        monitor = threading.Thread(
            target=_monitor_progress,
            args=(target, total_size, progress_callback, stop_monitor),
            daemon=True,
        )
        monitor.start()

        try:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    local_dir = snapshot_download(
                        repo_id=repo_id,
                        local_dir=str(target),
                        resume_download=True,
                        endpoint=endpoint,
                    )

                    # Signal download complete
                    if progress_callback and total_size > 0:
                        final = _count_dir_bytes(target)
                        progress_callback(final, final, 0)

                    logger.info(
                        "Model %s downloaded to %s", model_name, local_dir
                    )
                    return Path(local_dir)

                except Exception as exc:
                    logger.warning(
                        "Attempt %d/%d from %s failed: %s",
                        attempt,
                        _MAX_RETRIES,
                        endpoint,
                        exc,
                    )
                    last_error = exc
                    if attempt < _MAX_RETRIES:
                        continue

                    # All retries exhausted for this endpoint
                    break

        finally:
            stop_monitor.set()

        # Clean up partial download before trying next endpoint
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

    raise DownloadError(
        f"模型 {model_name} 下载失败（已尝试所有镜像端点）: {last_error}"
    )
