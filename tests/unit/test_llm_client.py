"""Tests for LLMClient — provider dispatch, timeout, cancel, is_configured."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from voiceime.llm.client import LLMClient
from voiceime.protocols import LLMResult


def _make_config(provider: str = "", model_id: str = "") -> MagicMock:
    config = MagicMock()
    defaults = {
        "llm.provider": provider,
        "llm.model_id": model_id,
    }
    config.get = lambda key, default=None: defaults.get(key, default)
    return config


def _make_keyring(has: dict | None = None) -> MagicMock:
    keyring = MagicMock()
    stored = has or {}

    def _get_key(p):
        return stored.get(p)

    keyring.has_key = lambda p: p in stored
    keyring.get_key = _get_key
    return keyring


class TestLLMClientConfigured:
    def test_should_not_be_configured_when_no_provider(self):
        config = _make_config()
        keyring = _make_keyring()
        client = LLMClient(config, keyring)
        assert client.is_configured is False

    def test_should_be_configured_for_ollama_without_key(self):
        config = _make_config(provider="ollama")
        keyring = _make_keyring()
        client = LLMClient(config, keyring)
        assert client.is_configured is True

    def test_should_not_be_configured_without_api_key(self):
        config = _make_config(provider="openai")
        keyring = _make_keyring()  # No keys
        client = LLMClient(config, keyring)
        assert client.is_configured is False

    def test_should_be_configured_with_api_key(self):
        config = _make_config(provider="openai")
        keyring = _make_keyring(has={"openai": "sk-test"})
        client = LLMClient(config, keyring)
        assert client.is_configured is True


class TestLLMClientPolish:
    def test_should_return_error_when_no_provider(self):
        config = _make_config()
        keyring = _make_keyring()
        client = LLMClient(config, keyring)
        result = client.polish("test")
        assert result.is_success is False
        assert "No provider" in result.error

    @patch("voiceime.llm.client.LLMClient._call_openai")
    def test_should_dispatch_to_openai(self, mock_call):
        mock_call.return_value = LLMResult(text="polished", is_success=True, error=None)
        config = _make_config(provider="openai", model_id="gpt-4o-mini")
        keyring = _make_keyring(has={"openai": "sk-test"})
        client = LLMClient(config, keyring)
        result = client.polish("test")
        assert result.is_success is True
        assert result.text == "polished"

    @patch("voiceime.llm.client.LLMClient._call_ollama")
    def test_should_dispatch_to_ollama(self, mock_call):
        mock_call.return_value = LLMResult(text="polished", is_success=True, error=None)
        config = _make_config(provider="ollama", model_id="qwen2.5:7b")
        keyring = _make_keyring()
        client = LLMClient(config, keyring)
        result = client.polish("test")
        assert result.is_success is True

    def test_should_preserve_original_on_timeout(self):
        config = _make_config(provider="ollama")
        keyring = _make_keyring()
        client = LLMClient(config, keyring)
        # Simulate timeout by making the executor submit hang
        with patch.object(client._executor, "submit", side_effect=TimeoutError()):
            result = client.polish("original")
        assert result.text == "original"
        assert result.is_success is False

    def test_should_cancel_in_progress_request(self):
        config = _make_config(provider="ollama")
        keyring = _make_keyring()
        client = LLMClient(config, keyring)
        client._cancel_event.clear()
        client.cancel()
        assert client._cancel_event.is_set()

    def test_should_call_with_custom_prompt(self):
        config = _make_config(provider="ollama")
        keyring = _make_keyring()
        client = LLMClient(config, keyring)
        with patch.object(client, "_dispatch") as mock_dispatch:
            mock_dispatch.return_value = LLMResult(text="ok", is_success=True, error=None)
            client.polish("test", system_prompt="custom prompt")
            call_args = mock_dispatch.call_args
            assert call_args[0][2] == "custom prompt"
