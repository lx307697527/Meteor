"""Tests for PostProcessPipeline — step toggling, order, polish."""

from unittest.mock import MagicMock

from voiceime.postprocess.pipeline import PostProcessPipeline
from voiceime.protocols import LLMResult, ProcessContext, ProcessResult


def _make_config(overrides: dict | None = None) -> MagicMock:
    defaults = {
        "postprocess.punct_normalize": True,
        "postprocess.t2s_enabled": False,
        "postprocess.hotword_enabled": True,
    }
    if overrides:
        defaults.update(overrides)
    config = MagicMock()
    config.get = lambda key, default=None: defaults.get(key, default)
    return config


def _make_hotword(entries: list[dict] | None = None) -> MagicMock:
    provider = MagicMock()
    provider.list_all.return_value = entries or []
    return provider


class TestPipelineProcess:
    def test_should_apply_punct_by_default(self):
        config = _make_config()
        pipeline = PostProcessPipeline(config)
        result = pipeline.process("你好,世界.")
        assert "punct" in result.steps_applied
        assert "，" in result.text

    def test_should_skip_punct_when_disabled(self):
        config = _make_config({"postprocess.punct_normalize": False})
        pipeline = PostProcessPipeline(config)
        result = pipeline.process("你好,世界.")
        assert "punct" not in result.steps_applied

    def test_should_apply_hotword_when_enabled(self):
        config = _make_config()
        hotword = _make_hotword([
            {"trigger": "你尼达", "replace": "UniData", "case_sensitive": False}
        ])
        pipeline = PostProcessPipeline(config, hotword_provider=hotword)
        result = pipeline.process("你尼达系统")
        assert "hotword" in result.steps_applied
        assert "UniData" in result.text

    def test_should_skip_hotword_when_disabled(self):
        config = _make_config({"postprocess.hotword_enabled": False})
        hotword = _make_hotword([
            {"trigger": "你尼达", "replace": "UniData", "case_sensitive": False}
        ])
        pipeline = PostProcessPipeline(config, hotword_provider=hotword)
        result = pipeline.process("你尼达系统")
        assert "hotword" not in result.steps_applied

    def test_should_apply_steps_in_order(self):
        config = _make_config({"postprocess.t2s_enabled": True, "postprocess.hotword_enabled": True})
        hotword = _make_hotword()
        pipeline = PostProcessPipeline(config, hotword_provider=hotword)
        result = pipeline.process("测试文本")
        assert result.steps_applied == ["punct", "converter", "hotword"]

    def test_should_return_empty_steps_for_empty_text(self):
        config = _make_config()
        pipeline = PostProcessPipeline(config)
        result = pipeline.process("")
        assert result.steps_applied == []
        assert result.text == ""

    def test_should_not_be_polished_after_process(self):
        config = _make_config()
        pipeline = PostProcessPipeline(config)
        result = pipeline.process("测试")
        assert result.is_polished is False


class TestPipelinePolish:
    def test_should_polish_when_llm_available(self):
        config = _make_config()
        llm = MagicMock()
        llm.is_configured = True
        llm.polish.return_value = LLMResult(text="润色后的文本", is_success=True, error=None)
        pipeline = PostProcessPipeline(config, llm_provider=llm)
        result = pipeline.polish_only("原始文本")
        assert result.is_polished is True
        assert result.text == "润色后的文本"
        assert "llm" in result.steps_applied

    def test_should_return_original_when_llm_fails(self):
        config = _make_config()
        llm = MagicMock()
        llm.is_configured = True
        llm.polish.return_value = LLMResult(text="", is_success=False, error="timeout")
        pipeline = PostProcessPipeline(config, llm_provider=llm)
        result = pipeline.polish_only("原始文本")
        assert result.is_polished is False
        assert result.text == "原始文本"

    def test_should_return_original_when_no_llm(self):
        config = _make_config()
        pipeline = PostProcessPipeline(config, llm_provider=None)
        result = pipeline.polish_only("原始文本")
        assert result.is_polished is False
        assert result.text == "原始文本"

    def test_should_return_original_when_llm_not_configured(self):
        config = _make_config()
        llm = MagicMock()
        llm.is_configured = False
        pipeline = PostProcessPipeline(config, llm_provider=llm)
        result = pipeline.polish_only("原始文本")
        assert result.is_polished is False

    def test_should_select_prompt_by_context(self):
        config = _make_config()
        llm = MagicMock()
        llm.is_configured = True
        llm.polish.return_value = LLMResult(text="result", is_success=True, error=None)
        pipeline = PostProcessPipeline(config, llm_provider=llm)
        ctx = ProcessContext(app_name="Code.exe", app_title="main.py")
        pipeline.polish_only("test", context=ctx)
        # Verify polish was called with a prompt
        call_args = llm.polish.call_args
        assert call_args is not None
        assert "system_prompt" in call_args.kwargs or len(call_args.args) > 1
