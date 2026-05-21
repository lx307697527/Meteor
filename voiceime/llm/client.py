"""LLMClient — Claude / OpenAI / Ollama text polish with timeout and cancel."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Protocol, runtime_checkable

from voiceime.protocols import LLMResult

logger = logging.getLogger("voiceime.llm.client")

_TIMEOUT_S = 10
_DNS_TIMEOUT_S = 5


class LLMAuthError(Exception):
    pass


class LLMConnectionError(Exception):
    pass


class LLMTimeoutError(Exception):
    pass


class _KeyringProvider(Protocol):
    def get_key(self, provider: str) -> str | None: ...
    def has_key(self, provider: str) -> bool: ...


class _ConfigProvider(Protocol):
    def get(self, key: str, default=None): ...


class LLMClient:
    """LLM text polish supporting Claude, OpenAI, and Ollama backends."""

    def __init__(self, config: _ConfigProvider, keyring: _KeyringProvider) -> None:
        self._config = config
        self._keyring = keyring
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._cancel_event = threading.Event()
        self._current_future: Future | None = None

    @property
    def is_configured(self) -> bool:
        provider = self._config.get("llm.provider", "")
        if not provider:
            return False
        if provider == "ollama":
            return True
        return self._keyring.has_key(provider)

    def polish(self, text: str, system_prompt: str | None = None) -> LLMResult:
        """Call LLM API to polish text. 10s timeout."""
        provider = self._config.get("llm.provider", "")
        if not provider:
            return LLMResult(text=text, is_success=False, error="No provider configured")

        self._cancel_event.clear()
        prompt = system_prompt or "请将以下文本润色为书面语，只输出润色后文本。"

        try:
            self._current_future = self._executor.submit(
                self._dispatch, provider, text, prompt
            )
            return self._current_future.result(timeout=_TIMEOUT_S)
        except TimeoutError:
            self._cancel_event.set()
            logger.warning("LLM polish timed out after %ds", _TIMEOUT_S)
            return LLMResult(text=text, is_success=False, error="timeout")
        except Exception as exc:
            logger.error("LLM polish error: %s", exc)
            return LLMResult(text=text, is_success=False, error=str(exc))

    def cancel(self) -> None:
        """Cancel in-progress LLM request."""
        self._cancel_event.set()
        if self._current_future and not self._current_future.done():
            self._current_future.cancel()

    def test_connection(self) -> bool:
        """Test whether the LLM API is reachable."""
        provider = self._config.get("llm.provider", "")
        if not provider:
            return False
        try:
            if provider == "ollama":
                import httpx
                resp = httpx.get("http://localhost:11434/api/tags", timeout=_DNS_TIMEOUT_S)
                return resp.status_code == 200
            return self.is_configured
        except Exception:
            return False

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    def _dispatch(self, provider: str, text: str, prompt: str) -> LLMResult:
        if provider == "claude":
            return self._call_claude(text, prompt)
        elif provider == "openai":
            return self._call_openai(text, prompt)
        elif provider == "ollama":
            return self._call_ollama(text, prompt)
        return LLMResult(text=text, is_success=False, error=f"Unknown provider: {provider}")

    def _call_claude(self, text: str, prompt: str) -> LLMResult:
        try:
            import anthropic
            api_key = self._keyring.get_key("claude")
            if not api_key:
                return LLMResult(text=text, is_success=False, error="No API key")
            model_id = self._config.get("llm.model_id", "claude-sonnet-4-20250514")
            client = anthropic.Anthropic(api_key=api_key, timeout=_TIMEOUT_S)
            message = client.messages.create(
                model=model_id,
                max_tokens=1024,
                system=prompt,
                messages=[{"role": "user", "content": text}],
            )
            result_text = message.content[0].text if message.content else text
            return LLMResult(text=result_text, is_success=True, error=None)
        except Exception as exc:
            return LLMResult(text=text, is_success=False, error=str(exc))

    def _call_openai(self, text: str, prompt: str) -> LLMResult:
        try:
            from openai import OpenAI
            api_key = self._keyring.get_key("openai")
            if not api_key:
                return LLMResult(text=text, is_success=False, error="No API key")
            model_id = self._config.get("llm.model_id", "gpt-4o-mini")
            client = OpenAI(api_key=api_key, timeout=_TIMEOUT_S)
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=1024,
            )
            result_text = response.choices[0].message.content or text
            return LLMResult(text=result_text, is_success=True, error=None)
        except Exception as exc:
            return LLMResult(text=text, is_success=False, error=str(exc))

    def _call_ollama(self, text: str, prompt: str) -> LLMResult:
        try:
            import httpx
            model_id = self._config.get("llm.model_id", "qwen2.5:7b")
            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model_id,
                    "prompt": f"{prompt}\n\n{text}",
                    "stream": False,
                },
                timeout=_TIMEOUT_S,
            )
            if response.status_code != 200:
                return LLMResult(text=text, is_success=False, error=f"HTTP {response.status_code}")
            data = response.json()
            result_text = data.get("response", text)
            return LLMResult(text=result_text, is_success=True, error=None)
        except Exception as exc:
            return LLMResult(text=text, is_success=False, error=str(exc))
