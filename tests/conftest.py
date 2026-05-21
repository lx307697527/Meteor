"""Global test fixtures for VoiceIME."""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temp APPDATA-equivalent directory."""
    return tmp_path / "VoiceIME"


@contextmanager
def _patch_config_paths(data_dir: Path):
    """Patch config_path and data_dir to use a temp directory."""
    config_file = data_dir / "config.json"
    data_dir.mkdir(parents=True, exist_ok=True)
    with (
        patch("voiceime.config.manager.config_path", return_value=config_file),
        patch("voiceime.config.manager.data_dir", return_value=data_dir),
    ):
        yield config_file


@pytest.fixture
def config_manager(tmp_data_dir):
    """Return a ConfigManager backed by a temp directory."""
    from voiceime.config.manager import ConfigManager

    with _patch_config_paths(tmp_data_dir) as cfg_file:
        mgr = ConfigManager()
        yield mgr


@pytest.fixture
def sample_pcm_1s():
    """1 second of 16 kHz Mono float32 sine wave."""
    t = np.linspace(0, 1.0, 16000, dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t)


@pytest.fixture
def sample_pcm_5s():
    """5 seconds of 16 kHz Mono float32 sine wave."""
    t = np.linspace(0, 5.0, 80000, dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t)


@pytest.fixture
def sample_pcm_silence():
    """1 second of silence."""
    return np.zeros(16000, dtype=np.float32)


@pytest.fixture
def qapp():
    """Provide a QApplication for tests that need Qt."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
