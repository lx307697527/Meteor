"""PostProcessPipeline — orchestrate punctuation, converter, hotword, and LLM steps."""

from __future__ import annotations

import logging

from voiceime.postprocess.converter import t2s
from voiceime.postprocess.hotword import apply_hotwords
from voiceime.postprocess.punct import normalize_punctuation, remove_trailing_particles
from voiceime.protocols import (
    ConfigProvider,
    HotwordProvider,
    LLMProvider,
    ProcessContext,
    ProcessResult,
)

logger = logging.getLogger("voiceime.postprocess.pipeline")


class PostProcessPipeline:
    """Configurable text post-processing pipeline."""

    def __init__(
        self,
        config: ConfigProvider,
        hotword_provider: HotwordProvider | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._config = config
        self._hotword = hotword_provider
        self._llm = llm_provider

    def process(
        self, text: str, context: ProcessContext | None = None
    ) -> ProcessResult:
        """Execute enabled post-processing steps in order."""
        if not text:
            return ProcessResult(text=text, is_polished=False, steps_applied=[])

        steps_applied: list[str] = []

        if self._config.get("postprocess.punct_normalize", True):
            text = normalize_punctuation(text)
            text = remove_trailing_particles(text)
            steps_applied.append("punct")

        if self._config.get("postprocess.t2s_enabled", False):
            text = t2s(text)
            steps_applied.append("converter")

        if (
            self._config.get("postprocess.hotword_enabled", True)
            and self._hotword is not None
        ):
            text = apply_hotwords(text, self._hotword)
            steps_applied.append("hotword")

        return ProcessResult(text=text, is_polished=False, steps_applied=steps_applied)

    def polish_only(
        self, text: str, context: ProcessContext | None = None,
        system_prompt: str | None = None,
    ) -> ProcessResult:
        """Execute only LLM polish, skipping other steps."""
        if not text:
            return ProcessResult(text=text, is_polished=False, steps_applied=[])

        if self._llm is None or not self._llm.is_configured:
            return ProcessResult(text=text, is_polished=False, steps_applied=[])

        try:
            if system_prompt is None:
                from voiceime.llm.prompts import get_prompt_for_context
                system_prompt = get_prompt_for_context(context)
            result = self._llm.polish(text, system_prompt=system_prompt)
            if not result.is_success:
                logger.warning("LLM polish failed: %s", result.error)
                return ProcessResult(text=text, is_polished=False, steps_applied=[])
            return ProcessResult(
                text=result.text, is_polished=True, steps_applied=["llm"]
            )
        except Exception as exc:
            logger.error("LLM polish error: %s", exc)
            return ProcessResult(text=text, is_polished=False, steps_applied=[])
