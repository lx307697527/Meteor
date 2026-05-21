"""Tests for LLM prompt selection."""

from voiceime.llm.prompts import get_prompt_for_context, DEFAULT_SYSTEM_PROMPT, CODE_COMMENT_PROMPT, BUSINESS_PROMPT
from voiceime.protocols import ProcessContext


class TestPromptSelection:
    def test_should_return_default_when_no_context(self):
        assert get_prompt_for_context(None) == DEFAULT_SYSTEM_PROMPT

    def test_should_return_default_when_no_app_name(self):
        ctx = ProcessContext(app_name=None, app_title=None)
        assert get_prompt_for_context(ctx) == DEFAULT_SYSTEM_PROMPT

    def test_should_return_code_prompt_for_vscode(self):
        ctx = ProcessContext(app_name="Code.exe", app_title="main.py")
        assert get_prompt_for_context(ctx) == CODE_COMMENT_PROMPT

    def test_should_return_code_prompt_for_idea(self):
        ctx = ProcessContext(app_name="idea64.exe", app_title="App.java")
        assert get_prompt_for_context(ctx) == CODE_COMMENT_PROMPT

    def test_should_return_business_prompt_for_word(self):
        ctx = ProcessContext(app_name="WINWORD.EXE", app_title="Report.docx")
        assert get_prompt_for_context(ctx) == BUSINESS_PROMPT

    def test_should_return_default_for_unknown_app(self):
        ctx = ProcessContext(app_name="chrome.exe", app_title="Google")
        assert get_prompt_for_context(ctx) == DEFAULT_SYSTEM_PROMPT
