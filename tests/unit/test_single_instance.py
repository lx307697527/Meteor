"""SingleInstance unit tests — F13: mutex acquisition, multi-instance prevention."""

from unittest.mock import MagicMock, patch

import pytest


class TestSingleInstance:
    """SingleInstance — named mutex lock for preventing multiple instances."""

    def test_should_acquire_lock_when_first_instance(self):
        import voiceime.utils.single_instance as si_mod

        with patch.object(si_mod._kernel32, "CreateMutexW", return_value=1), \
             patch.object(si_mod, "_kernel32") as mock_k32:
            mock_k32.CreateMutexW.return_value = 1
            mock_k32.GetLastError.return_value = 0
            mock_k32.CloseHandle = MagicMock()
            # Patch the module-level _kernel32 reference
            with patch.object(si_mod, "_kernel32", mock_k32):
                result = si_mod.request_single_instance_lock()
        assert result is True

    def test_should_fail_when_second_instance_tries(self):
        import voiceime.utils.single_instance as si_mod

        mock_k32 = MagicMock()
        mock_k32.CreateMutexW.return_value = 1
        mock_k32.GetLastError.return_value = 183  # ERROR_ALREADY_EXISTS
        mock_k32.CloseHandle = MagicMock()

        with patch.object(si_mod, "_kernel32", mock_k32):
            result = si_mod.request_single_instance_lock()
        assert result is False

    def test_should_release_lock_on_cleanup(self):
        import voiceime.utils.single_instance as si_mod

        mock_k32 = MagicMock()
        mock_k32.CreateMutexW.return_value = 1
        mock_k32.GetLastError.return_value = 0
        mock_k32.CloseHandle = MagicMock()

        with patch.object(si_mod, "_kernel32", mock_k32):
            si_mod.request_single_instance_lock()
            si_mod.release_single_instance_lock()
        mock_k32.CloseHandle.assert_called()
