"""RecorderStream unit tests — F02: recording lifecycle, PCM output, edge cases."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voiceime.protocols import AudioData


class TestRecorderStream:
    """RecorderStream — start/stop recording, PCM output, duration guards."""

    def test_should_not_be_recording_initially(self):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd"):
            rec = RecorderStream()
        assert rec.is_recording is False

    def test_should_return_zero_duration_when_not_recording(self):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd"):
            rec = RecorderStream()
        assert rec.duration_ms == 0

    def test_should_discard_recording_when_under_min_duration(self, sample_pcm_1s):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd.InputStream") as mock_is, \
             patch("voiceime.recorder.stream.get_default_device_id", return_value=0):
            mock_is.return_value.start = MagicMock()
            mock_is.return_value.stop = MagicMock()
            mock_is.return_value.close = MagicMock()

            rec = RecorderStream(min_record_ms=200)
            rec.start_recording()
            # Put a small buffer (< 200ms at 16kHz = < 3200 samples)
            rec._buffer.append(np.zeros(1000, dtype=np.float32))
            # Force recording flag off to simulate short duration
            import time
            time.sleep(0.01)
            result = rec.stop_recording()

        # Duration too short → empty pcm
        assert result.duration_ms < 200
        assert len(result.pcm) == 0

    def test_should_return_pcm_when_recording_valid(self, sample_pcm_1s):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd.InputStream") as mock_is, \
             patch("voiceime.recorder.stream.get_default_device_id", return_value=0):
            mock_is.return_value.start = MagicMock()
            mock_is.return_value.stop = MagicMock()
            mock_is.return_value.close = MagicMock()

            rec = RecorderStream(min_record_ms=0)  # Disable min duration check
            rec.start_recording()
            rec._buffer.append(sample_pcm_1s)
            result = rec.stop_recording()

        assert isinstance(result.pcm, np.ndarray)
        assert result.sample_rate == 16000
        assert len(result.pcm) > 0

    def test_should_return_empty_when_stop_without_start(self):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd"):
            rec = RecorderStream()
        result = rec.stop_recording()
        assert len(result.pcm) == 0
        assert result.duration_ms == 0

    def test_should_raise_device_not_found_when_no_mic(self):
        from voiceime.recorder.stream import DeviceNotFoundError, RecorderStream

        with patch("voiceime.recorder.stream.get_default_device_id", return_value=None):
            rec = RecorderStream()
            with pytest.raises(DeviceNotFoundError):
                rec.start_recording()

    def test_should_enforce_max_duration_watchdog(self):
        """Watchdog thread auto-stops recording after max_record_s."""
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd.InputStream") as mock_is, \
             patch("voiceime.recorder.stream.get_default_device_id", return_value=0):
            mock_is.return_value.start = MagicMock()
            mock_is.return_value.stop = MagicMock()
            mock_is.return_value.close = MagicMock()

            rec = RecorderStream(min_record_ms=0, max_record_s=1)
            rec.start_recording()
            assert rec.is_recording is True

            # Wait for watchdog to trigger (max_record_s=1, polls every 0.5s)
            import time
            time.sleep(1.5)
            assert rec.is_recording is False

    def test_should_return_empty_levels_when_not_recording(self):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd"):
            rec = RecorderStream()
        assert rec.current_levels == []

    def test_should_reset_levels_on_start_recording(self):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd.InputStream") as mock_is, \
             patch("voiceime.recorder.stream.get_default_device_id", return_value=0):
            mock_is.return_value.start = MagicMock()
            mock_is.return_value.stop = MagicMock()
            mock_is.return_value.close = MagicMock()

            rec = RecorderStream()
            rec._levels = [0.5, 0.3]  # Pre-populate
            rec.start_recording()
            assert rec.current_levels == []

    def test_should_update_levels_in_audio_callback(self):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd"):
            rec = RecorderStream()
        # Simulate audio callback
        indata = np.ones(1600, dtype=np.float32)
        rec._audio_callback(indata, 1600, None, None)
        assert len(rec.current_levels) == 1
        assert rec.current_levels[0] > 0
