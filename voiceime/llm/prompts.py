"""Default LLM prompts for text polish."""

from __future__ import annotations

from voiceime.protocols import ProcessContext

DEFAULT_SYSTEM_PROMPT = (
    "你是一个文本润色助手。请将以下口语化的中文文本改写为书面语，"
    "保持原意不变，不添加新内容。只输出润色后的文本。"
)

CODE_COMMENT_PROMPT = (
    "你是一个代码注释润色助手。请将以下语音识别结果整理为简洁清晰的代码注释，"
    "保持技术术语准确。只输出注释文本。"
)

BUSINESS_PROMPT = (
    "你是一个商务文档润色助手。请将以下文本改写为正式的商务书面语，"
    "用词专业得体，保持原意不变。只输出润色后的文本。"
)


def get_prompt_for_context(context: ProcessContext | None) -> str:
    """Select appropriate prompt based on app context."""
    if context is None or not context.app_name:
        return DEFAULT_SYSTEM_PROMPT

    app_lower = context.app_name.lower()

    code_apps = {"code.exe", "devenv.exe", "idea64.exe", "webstorm64.exe"}
    if any(app_lower.endswith(c) for c in code_apps):
        return CODE_COMMENT_PROMPT

    office_apps = {"winword.exe", "excel.exe", "powerpnt.exe", "wps.exe"}
    if any(app_lower.endswith(c) for c in office_apps):
        return BUSINESS_PROMPT

    return DEFAULT_SYSTEM_PROMPT


def get_prompt_from_overrides(overrides) -> str | None:
    """Extract system_prompt from ContextOverrides, if set."""
    if overrides is None:
        return None
    return overrides.system_prompt
