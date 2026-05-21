"""Foreground window detection via Win32 API for context-aware behavior."""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from collections import namedtuple

logger = logging.getLogger("voiceime.context.window")

WindowInfo = namedtuple("WindowInfo", ["app_name", "app_title"])

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_psapi = ctypes.windll.psapi

_user32.GetForegroundWindow.argtypes = []
_user32.GetForegroundWindow.restype = wintypes.HWND

_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD

_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE

_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.c_wchar_p, wintypes.DWORD]
_psapi.GetModuleFileNameExW.restype = wintypes.DWORD

_user32.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, wintypes.INT]
_user32.GetWindowTextW.restype = wintypes.INT

_PROCESS_QUERY_INFORMATION = 0x0400
_PROCESS_VM_READ = 0x0010
_MAX_PATH = 260
_MAX_TITLE = 512

# Cache for reducing API call frequency
_cached_info: WindowInfo | None = None
_cached_at: float = 0.0
_cache_ttl: float = 0.2  # 200ms default


def set_cache_ttl(ttl_ms: int) -> None:
    global _cache_ttl
    _cache_ttl = ttl_ms / 1000.0


def get_foreground_window() -> WindowInfo:
    """Return (app_name, app_title) of the current foreground window.

    Uses a short-lived cache to avoid hammering Win32 APIs.
    Falls back to WindowInfo("", "") on any failure.
    """
    global _cached_info, _cached_at

    now = time.monotonic()
    if _cached_info is not None and (now - _cached_at) < _cache_ttl:
        return _cached_info

    try:
        info = _query_foreground_window()
    except Exception as exc:
        logger.debug("Failed to query foreground window: %s", exc)
        info = WindowInfo("", "")

    _cached_info = info
    _cached_at = now
    return info


def _query_foreground_window() -> WindowInfo:
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return WindowInfo("", "")

    # Window title
    title_buf = ctypes.create_unicode_buffer(_MAX_TITLE)
    _user32.GetWindowTextW(hwnd, title_buf, _MAX_TITLE)
    title = title_buf.value

    # Process ID → process name
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    app_name = ""
    if pid.value:
        handle = _kernel32.OpenProcess(
            _PROCESS_QUERY_INFORMATION | _PROCESS_VM_READ, False, pid.value
        )
        if handle:
            try:
                name_buf = ctypes.create_unicode_buffer(_MAX_PATH)
                if _psapi.GetModuleFileNameExW(handle, None, name_buf, _MAX_PATH):
                    full_path = name_buf.value
                    app_name = full_path.rsplit("\\", 1)[-1]
            finally:
                _kernel32.CloseHandle(handle)

    return WindowInfo(app_name=app_name, app_title=title)
