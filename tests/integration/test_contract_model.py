"""CONTRACT-08: ModelProvider protocol compliance."""

from pathlib import Path
from unittest.mock import patch

import pytest

from voiceime.protocols import ModelProvider


def _create_model_files(model_dir: Path):
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.bin").write_bytes(b"fake")
    (model_dir / "config.json").write_text("{}")
    (model_dir / "vocabulary.json").write_text("你好")


@pytest.fixture(autouse=True)
def _disable_project_local_model(monkeypatch):
    """Disable project-local model lookup so tests use tmp_path."""
    monkeypatch.setenv("VOICEIME_LOCAL_MODEL_DIR", "")


class TestContractModelProvider:
    """Verify ModelManager satisfies ModelProvider protocol."""

    def test_should_satisfy_protocol_interface(self, tmp_path):
        from voiceime.model.manager import ModelManager

        mgr = ModelManager(tmp_path / "models")
        assert isinstance(mgr, ModelProvider)

    def test_should_have_required_methods(self, tmp_path):
        from voiceime.model.manager import ModelManager

        mgr = ModelManager(tmp_path / "models")
        assert hasattr(mgr, "ensure_model")
        assert hasattr(mgr, "verify_model")
        assert hasattr(mgr, "download_progress")
        assert hasattr(mgr, "available_models")

    def test_should_ensure_model_returns_path(self, tmp_path):
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "models"
        _create_model_files(models_dir / "large-v3-turbo")
        mgr = ModelManager(models_dir)
        path = mgr.ensure_model("large-v3-turbo", "int8")
        assert isinstance(path, Path)

    def test_should_verify_model_integrity(self, tmp_path):
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "models"
        _create_model_files(models_dir / "test-model")
        mgr = ModelManager(models_dir)
        assert mgr.verify_model(models_dir / "test-model") is True
