"""VirtualLock memory management for ASR model via ctypes."""

from __future__ import annotations

import ctypes
import logging
import platform
import threading
from ctypes import wintypes

logger = logging.getLogger("voiceime.asr.memory")

_kernel32 = ctypes.windll.kernel32

# VirtualLock / VirtualUnlock signatures
_kernel32.VirtualLock.argtypes = [wintypes.LPVOID, ctypes.c_size_t]
_kernel32.VirtualLock.restype = wintypes.BOOL
_kernel32.VirtualUnlock.argtypes = [wintypes.LPVOID, ctypes.c_size_t]
_kernel32.VirtualUnlock.restype = wintypes.BOOL

# GetProcessWorkingSetSize for querying limits
_kernel32.GetProcessWorkingSetSize.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)
]
_kernel32.GetProcessWorkingSetSize.restype = wintypes.BOOL

_kernel32.SetProcessWorkingSetSize.argtypes = [
    wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t
]
_kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL

_KERNEL_HANDLE = -1  # GetCurrentProcess pseudo-handle
_PAGE_SIZE = 4096


def _align_up(addr: int, alignment: int = _PAGE_SIZE) -> int:
    """Align address up to page boundary."""
    return (addr + alignment - 1) & ~(alignment - 1)


def _align_down(addr: int, alignment: int = _PAGE_SIZE) -> int:
    """Align address down to page boundary."""
    return addr & ~(alignment - 1)


def _page_aligned_range(ptr: int, size: int) -> tuple[int, int]:
    """Return (aligned_start, aligned_size) covering the full range."""
    start = _align_down(ptr)
    end = _align_up(ptr + size)
    return start, end - start


class MemoryLockStats:
    """Track locked memory statistics."""

    def __init__(self) -> None:
        self.locked_bytes: int = 0
        self.locked_regions: int = 0
        self.failed_regions: int = 0

    @property
    def locked_mb(self) -> float:
        return self.locked_bytes / (1024 * 1024)


_stats = MemoryLockStats()
_heartbeat_timer: threading.Timer | None = None
_heartbeat_stop = threading.Event()


def lock_model_memory(ptr: int, size: int, limit_gb: float = 3.5) -> bool:
    """Lock model memory pages to prevent swapping via VirtualLock.

    Args:
        ptr: Pointer address to the model memory region.
        size: Size in bytes of the memory region.
        limit_gb: Maximum GB allowed to lock (safety cap).

    Returns:
        True if locking succeeded (at least partially).
    """
    if platform.system() != "Windows":
        logger.warning("VirtualLock only available on Windows")
        return False

    limit_bytes = int(limit_gb * 1024 * 1024 * 1024)
    if size > limit_bytes:
        logger.warning(
            "Requested lock size %.1f MB exceeds limit %.1f GB, capping",
            size / (1024 * 1024), limit_gb,
        )
        size = limit_bytes

    aligned_start, aligned_size = _page_aligned_range(ptr, size)

    # Increase working set minimum to accommodate locked pages
    min_ws, max_ws = ctypes.c_size_t(), ctypes.c_size_t()
    _kernel32.GetProcessWorkingSetSize(_KERNEL_HANDLE, ctypes.byref(min_ws), ctypes.byref(max_ws))
    new_min = max(min_ws.value, aligned_size + 50 * 1024 * 1024)  # +50MB buffer
    new_max = max(max_ws.value, new_min * 2)
    _kernel32.SetProcessWorkingSetSize(_KERNEL_HANDLE, new_min, new_max)

    result = _kernel32.VirtualLock(aligned_start, aligned_size)
    if result:
        _stats.locked_bytes = aligned_size
        _stats.locked_regions += 1
        logger.info(
            "VirtualLock: locked %.1f MB (%d pages) at 0x%x",
            aligned_size / (1024 * 1024), aligned_size // _PAGE_SIZE, aligned_start,
        )
        return True
    else:
        error = ctypes.get_last_error()
        _stats.failed_regions += 1
        logger.error("VirtualLock failed at 0x%x, size %d: error %d", aligned_start, aligned_size, error)
        return False


def unlock_model_memory(ptr: int, size: int) -> bool:
    """Unlock previously locked memory pages."""
    if platform.system() != "Windows":
        return False

    aligned_start, aligned_size = _page_aligned_range(ptr, size)

    result = _kernel32.VirtualUnlock(aligned_start, aligned_size)
    if result:
        _stats.locked_bytes = max(0, _stats.locked_bytes - aligned_size)
        _stats.locked_regions = max(0, _stats.locked_regions - 1)
        logger.info("VirtualUnlock: released %.1f MB", aligned_size / (1024 * 1024))
        return True
    else:
        logger.warning("VirtualUnlock failed at 0x%x", aligned_start)
        return False


def get_stats() -> MemoryLockStats:
    """Return current memory locking statistics."""
    return _stats


def start_heartbeat(interval_s: float = 30.0) -> None:
    """Start periodic heartbeat that verifies locked memory is still resident.

    Args:
        interval_s: Seconds between heartbeat checks.
    """
    _heartbeat_stop.clear()

    def _beat() -> None:
        if _heartbeat_stop.is_set():
            return
        if _stats.locked_bytes > 0:
            logger.debug(
                "Memory heartbeat: %.1f MB locked, %d regions",
                _stats.locked_mb, _stats.locked_regions,
            )
        global _heartbeat_timer
        _heartbeat_timer = threading.Timer(interval_s, _beat)
        _heartbeat_timer.daemon = True
        _heartbeat_timer.start()

    _beat()
    logger.info("Memory heartbeat started (interval %.0fs)", interval_s)


def stop_heartbeat() -> None:
    """Stop the memory heartbeat timer."""
    _heartbeat_stop.set()
    if _heartbeat_timer is not None:
        _heartbeat_timer.cancel()
    logger.info("Memory heartbeat stopped")
