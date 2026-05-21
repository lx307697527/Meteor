"""Single-instance lock via Win32 named mutex."""

from __future__ import annotations

import ctypes
import logging

logger = logging.getLogger("voiceime.single_instance")

_kernel32 = ctypes.windll.kernel32

_MUTEX_NAME = "Global\\VoiceIME_SingleInstance"

_mutex_handle: int | None = None


def request_single_instance_lock() -> bool:
    """Try to acquire named mutex. Returns False if another instance is running."""
    global _mutex_handle
    handle = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle:
        logger.error("Failed to create mutex")
        return False

    last_error = _kernel32.GetLastError()
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        logger.warning("Another VoiceIME instance is already running")
        _kernel32.CloseHandle(handle)
        return False

    _mutex_handle = handle
    return True


def release_single_instance_lock() -> None:
    """Release the named mutex on shutdown."""
    global _mutex_handle
    if _mutex_handle:
        _kernel32.CloseHandle(_mutex_handle)
        _mutex_handle = None
