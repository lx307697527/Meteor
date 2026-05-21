"""CONTRACT-02: AudioProvider protocol compliance."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voiceime.protocols import AudioProvider


class TestContractAudioProvider:
    """Verify RecorderStream satisfies AudioProvider protocol."""

    def test_should_satisfy_protocol_interface(self):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd"):
            rec = RecorderStream()
        # Protocol structural check
        assert isinstance(rec, AudioProvider)

    def test_should_produce_audio_data_with_required_fields(self, sample_pcm_1s):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd.InputStream") as mock_is, \
             patch("voiceime.recorder.stream.get_default_device_id", return_value=0):
            mock_is.return_value.start = MagicMock()
            mock_is.return_value.stop = MagicMock()
            mock_is.return_value.close = MagicMock()

            rec = RecorderStream(min_record_ms=0)
            rec.start_recording()
            rec._buffer.append(sample_pcm_1s)
            result = rec.stop_recording()

        assert hasattr(result, "pcm")
        assert hasattr(result, "duration_ms")
        assert hasattr(result, "sample_rate")
        assert result.sample_rate == 16000

    def test_should_have_required_properties(self):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd"):
            rec = RecorderStream()
        assert hasattr(rec, "is_recording")
        assert hasattr(rec, "duration_ms")
        assert hasattr(rec, "devices")

    def test_should_support_start_and_stop(self, sample_pcm_1s):
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.stream.sd.InputStream") as mock_is, \
             patch("voiceime.recorder.stream.get_default_device_id", return_value=0):
            mock_is.return_value.start = MagicMock()
            mock_is.return_value.stop = MagicMock()
            mock_is.return_value.close = MagicMock()

            rec = RecorderStream(min_record_ms=0)
            rec.start_recording()
            assert rec.is_recording is True
            rec.stop_recording()
            assert rec.is_recording is False
