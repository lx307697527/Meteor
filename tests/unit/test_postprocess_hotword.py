"""Tests for hotword replacement."""

from unittest.mock import MagicMock

from voiceime.postprocess.hotword import apply_hotwords


class TestApplyHotwords:
    def test_should_replace_matching_trigger(self):
        provider = MagicMock()
        provider.list_all.return_value = [
            {"trigger": "你尼达", "replace": "UniData", "case_sensitive": False}
        ]
        result = apply_hotwords("欢迎来到你尼达", provider)
        assert result == "欢迎来到UniData"

    def test_should_replace_case_insensitive(self):
        provider = MagicMock()
        provider.list_all.return_value = [
            {"trigger": "hello", "replace": "world", "case_sensitive": False}
        ]
        result = apply_hotwords("Hello there", provider)
        assert result == "world there"

    def test_should_replace_case_sensitive(self):
        provider = MagicMock()
        provider.list_all.return_value = [
            {"trigger": "Hello", "replace": "World", "case_sensitive": True}
        ]
        result = apply_hotwords("Hello hello", provider)
        assert result == "World hello"

    def test_should_passthrough_when_no_match(self):
        provider = MagicMock()
        provider.list_all.return_value = []
        result = apply_hotwords("无匹配文本", provider)
        assert result == "无匹配文本"

    def test_should_handle_multiple_hotwords(self):
        provider = MagicMock()
        provider.list_all.return_value = [
            {"trigger": "你尼达", "replace": "UniData", "case_sensitive": False},
            {"trigger": "语音", "replace": "Voice", "case_sensitive": False},
        ]
        result = apply_hotwords("你尼达语音输入", provider)
        assert result == "UniDataVoice输入"

    def test_should_handle_empty_text(self):
        provider = MagicMock()
        provider.list_all.return_value = [
            {"trigger": "hello", "replace": "world", "case_sensitive": False}
        ]
        result = apply_hotwords("", provider)
        assert result == ""

    def test_should_handle_none_provider(self):
        result = apply_hotwords("text", None)
        assert result == "text"
