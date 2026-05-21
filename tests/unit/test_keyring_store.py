"""Tests for KeyringStore — API key CRUD via keyring."""

from unittest.mock import MagicMock, patch

from voiceime.keyring.store import KeyringStore


def _mock_keyring():
    kr = MagicMock()
    kr.errors.PasswordDeleteError = Exception
    return kr


class TestKeyringStore:
    @patch("voiceime.keyring.store._get_keyring")
    def test_should_save_key(self, mock_get):
        mock_kr = _mock_keyring()
        mock_get.return_value = mock_kr
        store = KeyringStore()
        store.save_key("openai", "sk-test123")
        mock_kr.set_password.assert_called_once_with("VoiceIME", "openai", "sk-test123")

    @patch("voiceime.keyring.store._get_keyring")
    def test_should_get_key(self, mock_get):
        mock_kr = _mock_keyring()
        mock_kr.get_password.return_value = "sk-test123"
        mock_get.return_value = mock_kr
        store = KeyringStore()
        result = store.get_key("openai")
        assert result == "sk-test123"
        mock_kr.get_password.assert_called_once_with("VoiceIME", "openai")

    @patch("voiceime.keyring.store._get_keyring")
    def test_should_return_none_when_key_missing(self, mock_get):
        mock_kr = _mock_keyring()
        mock_kr.get_password.return_value = None
        mock_get.return_value = mock_kr
        store = KeyringStore()
        assert store.get_key("nonexistent") is None

    @patch("voiceime.keyring.store._get_keyring")
    def test_should_delete_key(self, mock_get):
        mock_kr = _mock_keyring()
        mock_get.return_value = mock_kr
        store = KeyringStore()
        assert store.delete_key("openai") is True
        mock_kr.delete_password.assert_called_once_with("VoiceIME", "openai")

    @patch("voiceime.keyring.store._get_keyring")
    def test_should_return_false_deleting_nonexistent_key(self, mock_get):
        mock_kr = _mock_keyring()
        mock_kr.delete_password.side_effect = mock_kr.errors.PasswordDeleteError()
        mock_get.return_value = mock_kr
        store = KeyringStore()
        assert store.delete_key("nonexistent") is False

    @patch("voiceime.keyring.store._get_keyring")
    def test_should_check_has_key(self, mock_get):
        mock_kr = _mock_keyring()
        mock_kr.get_password.return_value = "key"
        mock_get.return_value = mock_kr
        store = KeyringStore()
        assert store.has_key("openai") is True

    @patch("voiceime.keyring.store._get_keyring")
    def test_should_report_no_key(self, mock_get):
        mock_kr = _mock_keyring()
        mock_kr.get_password.return_value = None
        mock_get.return_value = mock_kr
        store = KeyringStore()
        assert store.has_key("openai") is False
