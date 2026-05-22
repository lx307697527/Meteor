"""ModelManager unit tests — F10: model verification, download trigger."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _create_model_files(model_dir: Path):
    """Create minimal valid model files."""
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.bin").write_bytes(b"fake_model_data")
    (model_dir / "config.json").write_text("{}")
    (model_dir / "vocabulary.json").write_text("你好")


@pytest.fixture(autouse=True)
def _disable_project_local_model(monkeypatch):
    """Disable project-local model lookup so tests use tmp_path."""
    monkeypatch.setenv("VOICEIME_LOCAL_MODEL_DIR", "")


class TestModelManager:
    """ModelManager — verify, download, list models."""

    def test_should_return_local_path_when_model_exists(self, tmp_path):
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "models"
        model_dir = models_dir / "large-v3-turbo"
        _create_model_files(model_dir)

        mgr = ModelManager(models_dir)
        path = mgr.ensure_model("large-v3-turbo", "int8")
        assert path == model_dir

    def test_should_trigger_download_when_model_missing(self, tmp_path):
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "models"
        mgr = ModelManager(models_dir)

        with patch("voiceime.model.manager.download_model") as mock_dl:
            mock_dl.return_value = models_dir / "large-v3-turbo"
            mgr.ensure_model("large-v3-turbo", "int8")
        mock_dl.assert_called_once()

    def test_should_raise_error_when_download_fails(self, tmp_path):
        from voiceime.model.downloader import DownloadError
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "models"
        mgr = ModelManager(models_dir)

        with patch("voiceime.model.manager.download_model", side_effect=DownloadError("fail")):
            with pytest.raises(DownloadError):
                mgr.ensure_model("large-v3-turbo", "int8")

    def test_should_return_false_when_model_incomplete(self, tmp_path):
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "models"
        model_dir = models_dir / "broken"
        model_dir.mkdir(parents=True)
        (model_dir / "model.bin").write_bytes(b"data")
        # Missing config.json and vocabulary.txt

        mgr = ModelManager(models_dir)
        assert mgr.verify_model(model_dir) is False

    def test_should_return_true_when_model_complete(self, tmp_path):
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "models"
        model_dir = models_dir / "large-v3-turbo"
        _create_model_files(model_dir)

        mgr = ModelManager(models_dir)
        assert mgr.verify_model(model_dir) is True

    def test_should_return_false_when_model_dir_missing(self, tmp_path):
        from voiceime.model.manager import ModelManager

        mgr = ModelManager(tmp_path / "models")
        assert mgr.verify_model(tmp_path / "nonexistent") is False

    def test_should_list_available_models(self, tmp_path):
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "models"
        _create_model_files(models_dir / "large-v3-turbo")

        mgr = ModelManager(models_dir)
        assert "large-v3-turbo" in mgr.available_models

    def test_should_not_list_incomplete_models(self, tmp_path):
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "models"
        broken = models_dir / "broken"
        broken.mkdir(parents=True)
        (broken / "model.bin").write_bytes(b"data")

        mgr = ModelManager(models_dir)
        assert "broken" not in mgr.available_models

    def test_should_create_models_dir_on_init(self, tmp_path):
        from voiceime.model.manager import ModelManager

        models_dir = tmp_path / "new_models"
        ModelManager(models_dir)
        assert models_dir.exists()
