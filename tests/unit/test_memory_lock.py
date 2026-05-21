"""Tests for VirtualLock memory management — page alignment, locking, heartbeat."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from voiceime.asr.memory import (
    MemoryLockStats,
    _align_down,
    _align_up,
    _page_aligned_range,
    _PAGE_SIZE,
    get_stats,
    lock_model_memory,
    start_heartbeat,
    stop_heartbeat,
    unlock_model_memory,
)


class TestAlignFunctions:
    def test_should_align_up_to_page_boundary(self):
        assert _align_up(0) == 0
        assert _align_up(1) == _PAGE_SIZE
        assert _align_up(4095) == _PAGE_SIZE
        assert _align_up(4096) == 4096
        assert _align_up(5000) == 8192

    def test_should_align_down_to_page_boundary(self):
        assert _align_down(0) == 0
        assert _align_down(4095) == 0
        assert _align_down(4096) == 4096
        assert _align_down(5000) == 4096
        assert _align_down(8191) == 4096

    def test_should_align_up_already_aligned(self):
        assert _align_up(8192) == 8192

    def test_should_align_down_already_aligned(self):
        assert _align_down(8192) == 8192


class TestPageAlignedRange:
    def test_should_align_range_to_pages(self):
        ptr, size = _page_aligned_range(0, 4096)
        assert ptr == 0
        assert size == 4096

    def test_should_align_up_start_and_extend_end(self):
        ptr, size = _page_aligned_range(100, 100)
        assert ptr == 0
        assert size >= 200

    def test_should_align_down_start_and_up_end(self):
        ptr, size = _page_aligned_range(4096 + 1, 4096)
        assert ptr == 4096
        assert size == 8192

    def test_should_return_exact_for_page_aligned(self):
        ptr, size = _page_aligned_range(8192, 8192)
        assert ptr == 8192
        assert size == 8192


class TestMemoryLockStats:
    def test_should_track_locked_bytes(self):
        stats = MemoryLockStats()
        stats.locked_bytes = 1024 * 1024 * 2
        assert stats.locked_mb == 2.0

    def test_should_track_regions(self):
        stats = MemoryLockStats()
        stats.locked_regions = 3
        assert stats.locked_regions == 3

    def test_should_track_failed_regions(self):
        stats = MemoryLockStats()
        stats.failed_regions = 1
        assert stats.failed_regions == 1

    def test_should_not_go_negative_on_unlock(self):
        stats = MemoryLockStats()
        stats.locked_bytes = 100
        stats.locked_bytes = max(0, stats.locked_bytes - 200)
        assert stats.locked_bytes == 0


class TestLockModelMemory:
    @patch("voiceime.asr.memory.platform.system")
    def test_should_return_false_on_non_windows(self, mock_system):
        mock_system.return_value = "Linux"
        assert lock_model_memory(0x1000, 4096) is False

    @patch("voiceime.asr.memory.platform.system")
    def test_should_cap_size_when_exceeds_limit(self, mock_system):
        mock_system.return_value = "Windows"
        limit_gb = 0.001  # ~1MB limit
        large_size = 100 * 1024 * 1024  # 100MB
        with patch("voiceime.asr.memory._kernel32.VirtualLock", return_value=False):
            result = lock_model_memory(0x1000, large_size, limit_gb)
            assert result is False

    @patch("voiceime.asr.memory.platform.system")
    def test_should_return_true_on_success(self, mock_system):
        mock_system.return_value = "Windows"
        with (
            patch("voiceime.asr.memory._kernel32.VirtualLock", return_value=True),
            patch("voiceime.asr.memory._kernel32.GetProcessWorkingSetSize"),
            patch("voiceime.asr.memory._kernel32.SetProcessWorkingSetSize"),
        ):
            result = lock_model_memory(0x1000, 4096)
            assert result is True

    @patch("voiceime.asr.memory.platform.system")
    def test_should_return_false_on_virtual_lock_failure(self, mock_system):
        mock_system.return_value = "Windows"
        with (
            patch("voiceime.asr.memory._kernel32.VirtualLock", return_value=False),
            patch("voiceime.asr.memory._kernel32.GetProcessWorkingSetSize"),
            patch("voiceime.asr.memory._kernel32.SetProcessWorkingSetSize"),
            patch("voiceime.asr.memory.ctypes.get_last_error", return_value=5),
        ):
            result = lock_model_memory(0x1000, 4096)
            assert result is False

    @patch("voiceime.asr.memory.platform.system")
    def test_should_update_stats_on_success(self, mock_system):
        mock_system.return_value = "Windows"
        # Reset global stats before test
        get_stats().locked_bytes = 0
        get_stats().locked_regions = 0
        get_stats().failed_regions = 0
        with (
            patch("voiceime.asr.memory._kernel32.VirtualLock", return_value=True),
            patch("voiceime.asr.memory._kernel32.GetProcessWorkingSetSize"),
            patch("voiceime.asr.memory._kernel32.SetProcessWorkingSetSize"),
        ):
            lock_model_memory(0x1000, 8192)
            stats = get_stats()
            assert stats.locked_bytes == 8192
            assert stats.locked_regions == 1


class TestUnlockModelMemory:
    @patch("voiceime.asr.memory.platform.system")
    def test_should_return_false_on_non_windows(self, mock_system):
        mock_system.return_value = "Linux"
        assert unlock_model_memory(0x1000, 4096) is False

    @patch("voiceime.asr.memory.platform.system")
    def test_should_return_true_on_success(self, mock_system):
        mock_system.return_value = "Windows"
        with patch("voiceime.asr.memory._kernel32.VirtualUnlock", return_value=True):
            result = unlock_model_memory(0x1000, 4096)
            assert result is True

    @patch("voiceime.asr.memory.platform.system")
    def test_should_return_false_on_failure(self, mock_system):
        mock_system.return_value = "Windows"
        with patch("voiceime.asr.memory._kernel32.VirtualUnlock", return_value=False):
            result = unlock_model_memory(0x1000, 4096)
            assert result is False


class TestHeartbeat:
    def test_should_stop_heartbeat_immediately(self):
        stop_heartbeat()  # Should not raise even if never started

    @patch("voiceime.asr.memory.threading.Timer")
    def test_should_start_timer_on_start_heartbeat(self, mock_timer):
        start_heartbeat(interval_s=0.01)
        mock_timer.assert_called_once()
        stop_heartbeat()

    @patch("voiceime.asr.memory.threading.Timer")
    def test_should_stop_clears_event(self, mock_timer):
        start_heartbeat(interval_s=30.0)
        stop_heartbeat()
        # _heartbeat_stop should be set
        from voiceime.asr.memory import _heartbeat_stop
        assert _heartbeat_stop.is_set()

    def test_should_get_stats_after_operations(self):
        stats = get_stats()
        assert isinstance(stats, MemoryLockStats)
        # Stats should be the global singleton
        assert get_stats() is stats
