"""KeyringStore — API Key storage via Windows Credential Manager."""

from __future__ import annotations

import logging

logger = logging.getLogger("voiceime.keyring.store")

_SERVICE_NAME = "VoiceIME"

_keyring_module = None


def _get_keyring():
    global _keyring_module
    if _keyring_module is None:
        import keyring as _kr
        _keyring_module = _kr
    return _keyring_module


class KeyringStore:
    """Store and retrieve API keys using the system keyring."""

    def save_key(self, provider: str, api_key: str) -> None:
        kr = _get_keyring()
        kr.set_password(_SERVICE_NAME, provider, api_key)
        logger.info("API key saved for provider: %s", provider)

    def get_key(self, provider: str) -> str | None:
        kr = _get_keyring()
        return kr.get_password(_SERVICE_NAME, provider)

    def delete_key(self, provider: str) -> bool:
        kr = _get_keyring()
        try:
            kr.delete_password(_SERVICE_NAME, provider)
            logger.info("API key deleted for provider: %s", provider)
            return True
        except kr.errors.PasswordDeleteError:
            return False

    def has_key(self, provider: str) -> bool:
        return self.get_key(provider) is not None
