"""Tests for converter — traditional/simplified Chinese conversion."""

from unittest.mock import MagicMock, patch

from voiceime.postprocess.converter import t2s, s2t


class TestConverter:
    @patch("voiceime.postprocess.converter._get_t2s")
    def test_should_convert_t2s(self, mock_get):
        mock_converter = MagicMock()
        mock_converter.convert.return_value = "简体"
        mock_get.return_value = mock_converter
        result = t2s("繁體")
        assert result == "简体"

    @patch("voiceime.postprocess.converter._get_s2t")
    def test_should_convert_s2t(self, mock_get):
        mock_converter = MagicMock()
        mock_converter.convert.return_value = "繁體"
        mock_get.return_value = mock_converter
        result = s2t("简体")
        assert result == "繁體"

    @patch("voiceime.postprocess.converter._get_t2s")
    def test_should_return_original_when_opencc_unavailable(self, mock_get):
        mock_get.return_value = None
        result = t2s("繁體文字")
        assert result == "繁體文字"

    def test_should_handle_empty_string(self):
        assert t2s("") == ""
        assert s2t("") == ""
