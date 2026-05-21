"""CONTRACT-06: ConfigProvider protocol compliance."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from voiceime.protocols import ConfigProvider


@contextmanager
def _patched(tmp_data_dir: Path):
    config_file = tmp_data_dir / "config.json"
    tmp_data_dir.mkdir(parents=True, exist_ok=True)
    with (
        patch("voiceime.config.manager.config_path", return_value=config_file),
        patch("voiceime.config.manager.data_dir", return_value=tmp_data_dir),
    ):
        yield


class TestContractConfigProvider:
    """Verify ConfigManager satisfies ConfigProvider protocol."""

    def test_should_satisfy_protocol_interface(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir):
            mgr = ConfigManager()
        assert isinstance(mgr, ConfigProvider)

    def test_should_have_required_methods(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir):
            mgr = ConfigManager()
        assert hasattr(mgr, "get")
        assert hasattr(mgr, "set")
        assert hasattr(mgr, "reload")
        assert hasattr(mgr, "data_dir")

    def test_should_support_dot_path_access(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir):
            mgr = ConfigManager()
            assert mgr.get("asr.model") == "large-v3-turbo"

    def test_should_persist_and_reload(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir):
            mgr1 = ConfigManager()
            mgr1.set("asr.beam_size", 10)
            mgr2 = ConfigManager()
            assert mgr2.get("asr.beam_size") == 10
