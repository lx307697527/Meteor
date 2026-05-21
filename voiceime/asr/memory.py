"""VirtualLock memory management for ASR model — placeholder for Phase 2."""

from __future__ import annotations

import logging

logger = logging.getLogger("voiceime.asr.memory")


def lock_model_memory(ptr: int, size: int) -> bool:
    """Lock model memory pages to prevent swapping.

    Placeholder — will use ctypes VirtualLock in Phase 2.
    """
    logger.debug("Memory locking not yet implemented (Phase 2)")
    return True


def unlock_model_memory(ptr: int, size: int) -> bool:
    """Unlock previously locked memory pages."""
    logger.debug("Memory unlocking not yet implemented (Phase 2)")
    return True
