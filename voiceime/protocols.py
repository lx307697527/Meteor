# VoiceIME Protocol interfaces — shared contract between all modules.
# Modifications require confirmation from both infra-agent and pipeline-agent.

from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

import numpy as np

# ── Data Types ──────────────────────────────────────

HotKeyEvent = namedtuple("HotKeyEvent", ["key", "action"])

AudioData = namedtuple("AudioData", ["pcm", "duration_ms", "sample_rate"])

DeviceInfo = namedtuple("DeviceInfo", ["id", "name", "is_default"])

ASRResult = namedtuple("ASRResult", ["text", "language", "inference_ms", "segments"])

ProcessContext = namedtuple("ProcessContext", ["app_name", "app_title"])

ContextOverrides = namedtuple(
    "ContextOverrides",
    ["quick_mode", "polish_mode", "system_prompt", "punct_normalize", "t2s_enabled", "hotword_enabled"],
)

ProcessResult = namedtuple("ProcessResult", ["text", "is_polished", "steps_applied"])

OutputResult = namedtuple("OutputResult", ["success", "method", "error"])

LLMResult = namedtuple("LLMResult", ["text", "is_success", "error"])

DownloadProgress = namedtuple(
    "DownloadProgress", ["downloaded_bytes", "total_bytes", "speed_bps", "eta_seconds"]
)

TrayCommand = namedtuple("TrayCommand", ["action"])


@dataclass
class HistoryRecord:
    id: int | None = None
    created_at: str = ""
    text: str = ""
    raw_text: str | None = None
    language: str | None = None
    app_name: str | None = None
    app_title: str | None = None
    audio_duration_ms: int | None = None
    inference_time_ms: int | None = None
    is_polished: bool = False


# ── Protocol Interfaces ─────────────────────────────


@runtime_checkable
class ConfigProvider(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def reload(self) -> None: ...

    @property
    def data_dir(self) -> Path: ...


@runtime_checkable
class HotkeyProvider(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def set_callback(
        self, on_keydown: Callable[[], None], on_keyup: Callable[[], None]
    ) -> None: ...

    @property
    def current_hotkey(self) -> str: ...


@runtime_checkable
class AudioProvider(Protocol):
    def start_recording(self) -> None: ...
    def stop_recording(self) -> AudioData: ...

    @property
    def is_recording(self) -> bool: ...

    @property
    def duration_ms(self) -> int: ...

    @property
    def devices(self) -> list[DeviceInfo]: ...


@runtime_checkable
class ASRProvider(Protocol):
    def load_model(self) -> None: ...
    def transcribe(self, audio: np.ndarray) -> ASRResult: ...

    @property
    def is_loaded(self) -> bool: ...
    def unload_model(self) -> None: ...


@runtime_checkable
class PostProcessProvider(Protocol):
    def process(
        self, text: str, context: ProcessContext | None = None
    ) -> ProcessResult: ...
    def polish_only(
        self, text: str, context: ProcessContext | None = None
    ) -> ProcessResult: ...


@runtime_checkable
class OutputProvider(Protocol):
    def output(self, text: str) -> OutputResult: ...


@runtime_checkable
class HistoryProvider(Protocol):
    def save(self, record: HistoryRecord) -> int: ...
    def get_by_id(self, record_id: int) -> HistoryRecord | None: ...
    def search(
        self,
        query: str,
        app_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HistoryRecord]: ...
    def delete(self, record_id: int) -> bool: ...
    def clear_all(self) -> int: ...

    @property
    def total_count(self) -> int: ...


@runtime_checkable
class ModelProvider(Protocol):
    def ensure_model(self, model_name: str, quantization: str) -> Path: ...
    def verify_model(self, model_dir: Path) -> bool: ...

    @property
    def download_progress(self) -> DownloadProgress | None: ...

    @property
    def available_models(self) -> list[str]: ...


@runtime_checkable
class LLMProvider(Protocol):
    def polish(
        self, text: str, system_prompt: str | None = None
    ) -> LLMResult: ...
    def cancel(self) -> None: ...
    def test_connection(self) -> bool: ...

    @property
    def is_configured(self) -> bool: ...


@runtime_checkable
class HotwordProvider(Protocol):
    def find(self, trigger: str) -> str | None: ...
    def list_all(self) -> list[dict]: ...


@runtime_checkable
class KeyringProvider(Protocol):
    def save_key(self, provider: str, api_key: str) -> None: ...
    def get_key(self, provider: str) -> str | None: ...
    def delete_key(self, provider: str) -> bool: ...
    def has_key(self, provider: str) -> bool: ...


@runtime_checkable
class ContextProvider(Protocol):
    def get_context(self) -> ProcessContext: ...
    def match_rules(self, context: ProcessContext) -> ContextOverrides | None: ...
    def reload_rules(self) -> None: ...
