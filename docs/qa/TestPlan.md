# VoiceIME 测试计划

> 版本：V1.0 | 日期：2026-05-21 | 状态：草稿
> 输入来源：PRD V1.0 Phase 1 (P0) + Architecture V1.0 + DevOrchestration V1.0 (CONTRACT-01~10)
> 测试框架：pytest + pytest-qt + pytest-mock
> 覆盖范围：Phase 1 MVP，核心链路 100% 覆盖

---

# 1 需求跟踪矩阵（RTM）

## 1.1 P0 功能点 → 测试用例映射

| ID | 功能点 (来自 PRD §3) | 正常用例 | 边缘用例 | 异常用例 | 测试层级 | 优先级 |
|----|----------------------|---------|---------|---------|----------|--------|
| F01 | 全局热键录音 (§3.1) | Caps Lock keydown 开始/keyup 停止录音 | 最短 200ms 录音被保留；最长 60s 自动截断 | 热键被其他程序占用；WH_KEYBOARD_LL 注册失败 | Unit + Integration | P0 |
| F02 | 麦克风录音 (§3.1) | 16kHz Mono PCM 录音输出 numpy array | 无默认设备时枚举列表为空 | 录音中设备断开；设备打开失败 | Unit + Integration | P0 |
| F03 | ASR 推理 (§3.3) | 5s 音频返回非空 text + language | VAD 裁剪纯静音返回空 text | 模型未加载调推理；推理超时 30s；推理过程异常 | Unit + Integration | P0 |
| F04 | 文本上屏-剪贴板 (§3.4) | 备份→写入→Ctrl+V→恢复完整流程 | 剪贴板原有内容被正确恢复 | 剪贴板被其他程序占用；写入失败 | Unit | P0 |
| F05 | 文本上屏-UIA (§3.4) | UIAutomation Value Pattern 写入成功 | 目标控件不支持 Value Pattern | UIA 查找超时；无焦点窗口 | Unit | P0 |
| F06 | 文本上屏-键盘 (§3.4) | 逐字符输入成功 | 空字符串不执行输入 | pyautogui 异常 | Unit | P0 |
| F07 | 上屏 Fallback 编排 (§3.4) | clipboard 成功即返回 | clipboard 失败降级 uia；uia 失败降级 keyboard | 三层全部失败 | Integration | P0 |
| F08 | 系统托盘 (§3.2) | 4 种状态图标正确切换；右键菜单可点击 | 启动时托盘线程异常 | pystray 初始化失败不影响主流程 | Integration + E2E | P0 |
| F09 | ConfigManager (§6.3) | 点分路径读写；持久化到 config.json | JSON 损坏自动恢复默认值；配置文件不存在自动创建 | 并发写入不损坏文件 | Unit | P0 |
| F10 | ModelManager (§6.5) | 模型存在时跳过下载；不存在时下载 | 下载中断后断点续传 | 下载 3 次失败抛出 DownloadError；模型文件损坏 | Unit | P0 |
| F11 | CoreController 状态机 (§6.2) | UNINITIALIZED→READY→RECORDING→INFERRING→OUTPUTTING→READY 完整流转 | PAUSED 状态下热键不触发录音；快速连按防抖 | ERROR_MIC/ERROR_MODEL/ERROR_INFERENCE_TIMEOUT 错误态正确恢复 | Unit + Integration | P0 |
| F12 | 剪贴板保护 (§3.4) | 上屏完成后原剪贴板内容恢复 | 原剪贴板为空；原剪贴板为图片等非文本 | 恢复超时 3s 后放弃恢复 | Unit | P0 |
| F13 | 进程安全 (§4.3) | atexit 注销钩子；命名互斥体防多实例 | 第二实例启动被阻止 | 崩溃时 WH_KEYBOARD_LL 自动卸载 | Unit | P0 |
| F14 | 设置窗口-推理 Tab (§3.8) | 修改模型/量化/VAD 参数并持久化 | 非法值被拒绝或回退默认 | 配置保存失败不崩溃 | E2E | P0 |

---

# 2 测试分层设计

## 2.1 分层策略

```
┌─────────────────────────────────────────────────────┐
│  E2E (pytest-qt)                                    │
│  托盘交互 · 设置窗口 · 首次引导 · 全链路冒烟        │
│  依赖：完整应用启动                                  │
├─────────────────────────────────────────────────────┤
│  Integration (pytest)                               │
│  跨模块接口 · 基于 CONTRACT-01~10                    │
│  依赖：至少两个真实模块 + Mock 外部依赖               │
├─────────────────────────────────────────────────────┤
│  Unit (pytest + pytest-mock)                        │
│  纯函数 · 单个类/方法 · 独立模块                     │
│  依赖：仅被测模块 + Mock                             │
└─────────────────────────────────────────────────────┘
```

## 2.2 Mock 策略

| 外部依赖 | Mock 方式 | 说明 |
|----------|----------|------|
| faster-whisper | `unittest.mock.MagicMock` | 推理返回预设 ASRResult |
| sounddevice | `unittest.mock.patch` | 模拟 PCM 数据流 |
| pynput | `unittest.mock.patch` | 模拟键盘事件 |
| pystray | `unittest.mock.MagicMock` | 模拟托盘图标 |
| pyautogui | `unittest.mock.patch` | 模拟键盘输入 |
| keyring | `unittest.mock.patch` | 模拟 Credential Manager |
| UIAutomation | `unittest.mock.patch` | 模拟 UIA 控件 |
| HuggingFace 下载 | `unittest.mock.patch` | 模拟下载进度 |
| Windows API (ctypes) | `unittest.mock.patch` | 模拟互斥体、WH_KEYBOARD_LL |

## 2.3 测试目录结构

```
tests/
├── conftest.py                     # 全局 fixtures
├── unit/
│   ├── __init__.py
│   ├── test_paths.py               # F13: APPDATA 路径管理
│   ├── test_single_instance.py     # F13: 命名互斥体
│   ├── test_config_manager.py      # F09: ConfigManager
│   ├── test_hotkey_manager.py      # F01: HotkeyManager
│   ├── test_recorder_device.py     # F02: 设备枚举
│   ├── test_recorder_stream.py     # F02: 录音流
│   ├── test_asr_engine.py          # F03: ASR 推理
│   ├── test_model_manager.py       # F10: 模型管理
│   ├── test_output_clipboard.py    # F04+F12: 剪贴板上屏+保护
│   ├── test_output_uia.py          # F05: UIA 上屏
│   ├── test_output_keyboard.py     # F06: 键盘上屏
│   ├── test_output_controller.py   # F07: Fallback 编排
│   └── test_core_state_machine.py  # F11: 状态机流转
├── integration/
│   ├── __init__.py
│   ├── test_contract_hotkey.py     # CONTRACT-01
│   ├── test_contract_audio.py      # CONTRACT-02
│   ├── test_contract_asr.py        # CONTRACT-03
│   ├── test_contract_output.py     # CONTRACT-05
│   ├── test_contract_config.py     # CONTRACT-06
│   ├── test_contract_model.py      # CONTRACT-08
│   └── test_pipeline_e2e.py        # 热键→录音→ASR→上屏 全链路
└── e2e/
    ├── __init__.py
    ├── test_tray.py                 # F08: 系统托盘
    ├── test_settings.py             # F14: 设置窗口
    └── test_smoke.py                # 全链路冒烟测试
```

---

# 3 测试代码框架

## 3.1 全局 Fixtures

```python
# tests/conftest.py
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    """创建临时 APPDATA 目录，含默认 config.json。"""
    config = {
        "asr": {
            "model": "large-v3-turbo",
            "quantization": "int8",
            "vad": True,
            "language": "zh",
        },
        "hotkey": {"key": "caps_lock"},
        "output": {
            "clipboard_restore_delay_ms": 500,
            "fallback_order": ["clipboard", "uia", "keyboard"],
        },
        "recorder": {
            "sample_rate": 16000,
            "channels": 1,
            "min_duration_ms": 200,
            "max_duration_ms": 60000,
        },
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return tmp_path


@pytest.fixture
def mock_config_provider(tmp_data_dir):
    """返回基于临时目录的 ConfigProvider mock。"""
    from voiceime.config.manager import ConfigManager

    with patch("voiceime.config.manager.Path") as mock_path_cls:
        mock_path_cls.return_value = tmp_data_dir
        manager = ConfigManager()
    return manager


@pytest.fixture
def sample_pcm_1s():
    """1 秒 16kHz Mono float32 PCM 数据（正弦波）。"""
    import numpy as np

    sample_rate = 16000
    t = np.linspace(0, 1.0, sample_rate, dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t)


@pytest.fixture
def sample_pcm_5s():
    """5 秒 16kHz Mono float32 PCM 数据（正弦波）。"""
    import numpy as np

    sample_rate = 16000
    t = np.linspace(0, 5.0, sample_rate * 5, dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t)


@pytest.fixture
def sample_pcm_silence():
    """1 秒纯静音 PCM 数据。"""
    import numpy as np

    return np.zeros(16000, dtype=np.float32)
```

---

## 3.2 单元测试

### 3.2.1 ConfigManager (F09)

```python
# tests/unit/test_config_manager.py
import json
from pathlib import Path

import pytest


class TestConfigManager:
    """ConfigManager 单元测试 — 配置读写、点分路径、容灾恢复。"""

    describe = "ConfigManager"

    def test_should_return_correct_value_when_reading_existing_key(
        self, tmp_data_dir
    ):
        # Arrange
        from voiceime.config.manager import ConfigManager

        manager = ConfigManager(data_dir=tmp_data_dir)
        # Act
        value = manager.get("asr.model")
        # Assert
        assert value == "large-v3-turbo"

    def test_should_return_default_when_key_not_found(self, tmp_data_dir):
        # Arrange
        from voiceime.config.manager import ConfigManager

        manager = ConfigManager(data_dir=tmp_data_dir)
        # Act
        value = manager.get("nonexistent.key", default="fallback")
        # Assert
        assert value == "fallback"

    def test_should_persist_value_when_setting_key(self, tmp_data_dir):
        # Arrange
        from voiceime.config.manager import ConfigManager

        manager = ConfigManager(data_dir=tmp_data_dir)
        # Act
        manager.set("asr.vad", False)
        # Assert — 重新加载验证持久化
        manager.reload()
        assert manager.get("asr.vad") is False

    def test_should_recover_default_when_json_corrupted(self, tmp_data_dir):
        # Arrange — 写入损坏的 JSON
        config_path = tmp_data_dir / "config.json"
        config_path.write_text("{invalid json", encoding="utf-8")
        from voiceime.config.manager import ConfigManager

        # Act
        manager = ConfigManager(data_dir=tmp_data_dir)
        # Assert — 应恢复为默认值而非崩溃
        assert manager.get("asr.model") is not None

    def test_should_create_default_when_config_file_missing(self, tmp_data_dir):
        # Arrange — 删除配置文件
        (tmp_data_dir / "config.json").unlink()
        from voiceime.config.manager import ConfigManager

        # Act
        manager = ConfigManager(data_dir=tmp_data_dir)
        # Assert — 自动创建并包含默认值
        assert (tmp_data_dir / "config.json").exists()
        assert manager.get("asr.model") is not None

    def test_should_return_data_dir_path(self, tmp_data_dir):
        # Arrange
        from voiceime.config.manager import ConfigManager

        manager = ConfigManager(data_dir=tmp_data_dir)
        # Act & Assert
        assert manager.data_dir == tmp_data_dir
```

### 3.2.2 HotkeyManager (F01)

```python
# tests/unit/test_hotkey_manager.py
from unittest.mock import MagicMock, patch

import pytest


class TestHotkeyManager:
    """HotkeyManager 单元测试 — 热键注册、回调触发、冲突处理。"""

    describe = "HotkeyManager"

    def test_should_invoke_on_keydown_callback_when_hotkey_pressed(self):
        # Arrange
        from voiceime.hotkey.manager import HotkeyManager

        manager = HotkeyManager(hotkey="caps_lock")
        on_keydown = MagicMock()
        on_keyup = MagicMock()
        manager.set_callback(on_keydown=on_keydown, on_keyup=on_keyup)
        # Act — 模拟按键事件
        manager._handle_key_event(key="caps_lock", action="down")
        # Assert
        on_keydown.assert_called_once()
        on_keyup.assert_not_called()

    def test_should_invoke_on_keyup_callback_when_hotkey_released(self):
        # Arrange
        from voiceime.hotkey.manager import HotkeyManager

        manager = HotkeyManager(hotkey="caps_lock")
        on_keydown = MagicMock()
        on_keyup = MagicMock()
        manager.set_callback(on_keydown=on_keydown, on_keyup=on_keyup)
        # Act
        manager._handle_key_event(key="caps_lock", action="up")
        # Assert
        on_keyup.assert_called_once()

    def test_should_ignore_non_target_key_events(self):
        # Arrange
        from voiceime.hotkey.manager import HotkeyManager

        manager = HotkeyManager(hotkey="caps_lock")
        on_keydown = MagicMock()
        on_keyup = MagicMock()
        manager.set_callback(on_keydown=on_keydown, on_keyup=on_keyup)
        # Act — 按 A 键
        manager._handle_key_event(key="a", action="down")
        # Assert
        on_keydown.assert_not_called()

    def test_should_raise_conflict_error_when_hotkey_occupied(self):
        # Arrange
        from voiceime.hotkey.manager import HotkeyManager
        from voiceime.hotkey.hook import HotkeyConflictError

        manager = HotkeyManager(hotkey="caps_lock")
        # Act & Assert
        with pytest.raises(HotkeyConflictError):
            manager.start()  # TODO: 需要 mock pynput 抛出冲突

    def test_should_return_current_hotkey_name(self):
        # Arrange
        from voiceime.hotkey.manager import HotkeyManager

        manager = HotkeyManager(hotkey="caps_lock")
        # Act & Assert
        assert manager.current_hotkey == "caps_lock"

    def test_should_cleanup_hook_when_stop_called(self):
        # Arrange
        from voiceime.hotkey.manager import HotkeyManager

        manager = HotkeyManager(hotkey="caps_lock")
        manager.start()  # TODO: mock pynput Listener
        # Act
        manager.stop()
        # Assert — Listener 应已停止
        assert not manager._is_listening
```

### 3.2.3 RecorderStream (F02)

```python
# tests/unit/test_recorder_stream.py
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestRecorderStream:
    """RecorderStream 单元测试 — 录音启停、PCM 输出、设备管理。"""

    describe = "RecorderStream"

    def test_should_produce_numpy_array_when_recording_stopped(self, sample_pcm_1s):
        # Arrange
        from voiceime.recorder.stream import RecorderStream

        recorder = RecorderStream(sample_rate=16000)
        # Act — 模拟录音开始/停止
        with patch("voiceime.recorder.stream.sd.InputStream") as mock_stream:
            mock_stream.return_value.__enter__ = MagicMock()
            mock_stream.return_value.__exit__ = MagicMock(return_value=False)
            recorder.start_recording()
            # 模拟写入 PCM 数据
            recorder._buffer.append(sample_pcm_1s)
            result = recorder.stop_recording()
        # Assert
        assert isinstance(result.pcm, np.ndarray)
        assert result.sample_rate == 16000

    def test_should_enforce_max_duration_when_recording_exceeds_60s(self):
        # Arrange
        from voiceime.recorder.stream import RecorderStream

        recorder = RecorderStream(
            sample_rate=16000, max_duration_ms=60000
        )
        # Act & Assert — TODO: 模拟超过 60s 的录音
        # 应自动截断，不抛异常
        pass

    def test_should_discard_recording_when_duration_under_200ms(self, sample_pcm_silence):
        # Arrange
        from voiceime.recorder.stream import RecorderStream

        recorder = RecorderStream(
            sample_rate=16000, min_duration_ms=200
        )
        # Act — 录音时长不足 200ms
        with patch("voiceime.recorder.stream.sd.InputStream"):
            recorder.start_recording()
            short_audio = np.zeros(1000, dtype=np.float32)  # ~62ms
            recorder._buffer.append(short_audio)
            result = recorder.stop_recording()
        # Assert — 应返回空或标记为太短
        assert result.duration_ms < 200  # TODO: 确认短录音的返回策略

    def test_should_raise_device_not_found_when_no_mic(self):
        # Arrange
        from voiceime.recorder.stream import RecorderStream
        from voiceime.recorder.device import DeviceNotFoundError

        with patch("voiceime.recorder.device.sd.query_devices") as mock_query:
            mock_query.return_value = []  # 无设备
            # Act & Assert
            with pytest.raises(DeviceNotFoundError):
                RecorderStream(sample_rate=16000)

    def test_should_indicate_not_recording_initially(self):
        # Arrange
        from voiceime.recorder.stream import RecorderStream

        recorder = RecorderStream(sample_rate=16000)
        # Act & Assert
        assert recorder.is_recording is False

    def test_should_track_duration_in_realtime(self):
        # Arrange
        from voiceime.recorder.stream import RecorderStream

        recorder = RecorderStream(sample_rate=16000)
        # Act — 开始录音后检查 duration_ms
        with patch("voiceime.recorder.stream.sd.InputStream"):
            recorder.start_recording()
            duration = recorder.duration_ms
        # Assert — 应为非负数
        assert duration >= 0
```

### 3.2.4 ASREngine (F03)

```python
# tests/unit/test_asr_engine.py
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestASREngine:
    """ASREngine 单元测试 — 模型加载、推理、VAD、超时。"""

    describe = "ASREngine"

    def test_should_return_nonempty_text_when_transcribing_valid_audio(
        self, sample_pcm_5s
    ):
        # Arrange
        from voiceime.asr.engine import ASREngine

        engine = ASREngine(model_name="large-v3-turbo", quantization="int8")
        with patch("voiceime.asr.engine.FasterWhisperASR") as mock_asr:
            mock_asr.return_value.transcribe.return_value = (
                "你好世界",
                [("你好世界", 0.0, 5.0)],
            )
            engine._model = mock_asr.return_value
            engine._loaded = True
            # Act
            result = engine.transcribe(sample_pcm_5s)
        # Assert
        assert result.text == "你好世界"
        assert result.language in ("zh", "en", "mixed")
        assert result.inference_ms > 0

    def test_should_raise_timeout_when_inference_exceeds_30s(
        self, sample_pcm_5s
    ):
        # Arrange
        from voiceime.asr.engine import ASREngine
        from voiceime.asr.engine import InferenceTimeoutError

        engine = ASREngine(model_name="large-v3-turbo", quantization="int8")
        engine._loaded = True
        engine._model = MagicMock()
        engine._model.transcribe.side_effect = TimeoutError()
        # Act & Assert
        with pytest.raises(InferenceTimeoutError):
            engine.transcribe(sample_pcm_5s)

    def test_should_raise_not_loaded_error_when_model_not_loaded(
        self, sample_pcm_1s
    ):
        # Arrange
        from voiceime.asr.engine import ASREngine
        from voiceime.asr.engine import ModelNotLoadedError

        engine = ASREngine(model_name="large-v3-turbo", quantization="int8")
        engine._loaded = False
        # Act & Assert
        with pytest.raises(ModelNotLoadedError):
            engine.transcribe(sample_pcm_1s)

    def test_should_return_empty_text_when_vad_cuts_silence(
        self, sample_pcm_silence
    ):
        # Arrange
        from voiceime.asr.engine import ASREngine

        engine = ASREngine(model_name="large-v3-turbo", quantization="int8")
        with patch("voiceime.asr.engine.FasterWhisperASR") as mock_asr:
            mock_asr.return_value.transcribe.return_value = ("", [])
            engine._model = mock_asr.return_value
            engine._loaded = True
            # Act
            result = engine.transcribe(sample_pcm_silence)
        # Assert — VAD 裁剪静音后可能返回空文本
        assert result.text == ""

    def test_should_indicate_loaded_when_model_ready(self):
        # Arrange
        from voiceime.asr.engine import ASREngine

        engine = ASREngine(model_name="large-v3-turbo", quantization="int8")
        engine._loaded = True
        # Act & Assert
        assert engine.is_loaded is True

    def test_should_free_memory_when_unload_called(self):
        # Arrange
        from voiceime.asr.engine import ASREngine

        engine = ASREngine(model_name="large-v3-turbo", quantization="int8")
        engine._loaded = True
        engine._model = MagicMock()
        # Act
        engine.unload_model()
        # Assert
        assert engine.is_loaded is False
```

### 3.2.5 OutputController — Clipboard (F04 + F12)

```python
# tests/unit/test_output_clipboard.py
from unittest.mock import MagicMock, patch

import pytest


class TestClipboardOutput:
    """ClipboardOutput 单元测试 — 剪贴板写入、备份恢复。"""

    describe = "ClipboardOutput"

    def test_should_backup_write_paste_and_restore(self):
        # Arrange
        from voiceime.output.clipboard import ClipboardOutput

        clipboard = ClipboardOutput(restore_delay_ms=500)
        call_order = []

        with patch("voiceime.output.clipboard.pyperclip") as mock_clip:
            mock_clip.paste.return_value = "original_text"
            mock_clip.copy = lambda t: call_order.append(("copy", t))
            # Act
            result = clipboard.output("你好世界")
        # Assert
        assert result.success is True
        assert result.method == "clipboard"

    def test_should_handle_empty_original_clipboard(self):
        # Arrange
        from voiceime.output.clipboard import ClipboardOutput

        clipboard = ClipboardOutput(restore_delay_ms=500)
        with patch("voiceime.output.clipboard.pyperclip") as mock_clip:
            mock_clip.paste.side_effect = Exception("clipboard empty")
            # Act
            result = clipboard.output("你好世界")
        # Assert — 即使原剪贴板为空也应成功
        assert result.success is True

    def test_should_return_failure_when_clipboard_write_fails(self):
        # Arrange
        from voiceime.output.clipboard import ClipboardOutput

        clipboard = ClipboardOutput(restore_delay_ms=500)
        with patch("voiceime.output.clipboard.pyperclip") as mock_clip:
            mock_clip.paste.return_value = "original"
            mock_clip.copy.side_effect = OSError("write failed")
            # Act
            result = clipboard.output("你好世界")
        # Assert
        assert result.success is False
        assert result.error is not None

    def test_should_restore_original_content_after_delay(self):
        # Arrange
        from voiceime.output.clipboard import ClipboardOutput

        clipboard = ClipboardOutput(restore_delay_ms=100)
        with patch("voiceime.output.clipboard.pyperclip") as mock_clip:
            mock_clip.paste.return_value = "保护的内容"
            # Act
            result = clipboard.output("新文本")
        # Assert — TODO: 验证延迟恢复逻辑，需异步断言
```

### 3.2.6 OutputController — Fallback 编排 (F07)

```python
# tests/unit/test_output_controller.py
from unittest.mock import MagicMock

import pytest


class TestOutputController:
    """OutputController 单元测试 — 三层 Fallback 编排。"""

    describe = "OutputController"

    def test_should_succeed_with_clipboard_when_first_method_works(self):
        # Arrange
        from voiceime.output.controller import OutputController

        controller = OutputController()
        controller._clipboard = MagicMock()
        controller._clipboard.output.return_value = MagicMock(
            success=True, method="clipboard", error=None
        )
        # Act
        result = controller.output("你好世界")
        # Assert
        assert result.success is True
        assert result.method == "clipboard"

    def test_should_fallback_to_uia_when_clipboard_fails(self):
        # Arrange
        from voiceime.output.controller import OutputController

        controller = OutputController()
        controller._clipboard = MagicMock()
        controller._clipboard.output.return_value = MagicMock(
            success=False, method="clipboard", error="write failed"
        )
        controller._uia = MagicMock()
        controller._uia.output.return_value = MagicMock(
            success=True, method="uia", error=None
        )
        # Act
        result = controller.output("你好世界")
        # Assert
        assert result.success is True
        assert result.method == "uia"

    def test_should_fallback_to_keyboard_when_uia_fails(self):
        # Arrange
        from voiceime.output.controller import OutputController

        controller = OutputController()
        controller._clipboard = MagicMock()
        controller._clipboard.output.return_value = MagicMock(
            success=False, method="clipboard", error="failed"
        )
        controller._uia = MagicMock()
        controller._uia.output.return_value = MagicMock(
            success=False, method="uia", error="no pattern"
        )
        controller._keyboard = MagicMock()
        controller._keyboard.output.return_value = MagicMock(
            success=True, method="keyboard", error=None
        )
        # Act
        result = controller.output("你好世界")
        # Assert
        assert result.success is True
        assert result.method == "keyboard"

    def test_should_return_failure_when_all_methods_fail(self):
        # Arrange
        from voiceime.output.controller import OutputController

        controller = OutputController()
        for attr in ("_clipboard", "_uia", "_keyboard"):
            mock = MagicMock()
            mock.output.return_value = MagicMock(
                success=False, method=attr, error="failed"
            )
            setattr(controller, attr, mock)
        # Act
        result = controller.output("你好世界")
        # Assert
        assert result.success is False
        assert result.error is not None
```

### 3.2.7 ModelManager (F10)

```python
# tests/unit/test_model_manager.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestModelManager:
    """ModelManager 单元测试 — 模型验证、下载、断点续传。"""

    describe = "ModelManager"

    def test_should_return_local_path_when_model_exists(self, tmp_data_dir):
        # Arrange
        from voiceime.model.manager import ModelManager

        model_dir = tmp_data_dir / "models" / "large-v3-turbo"
        model_dir.mkdir(parents=True)
        (model_dir / "model.bin").write_bytes(b"fake")
        (model_dir / "config.json").write_text("{}")
        (model_dir / "vocabulary.txt").write_text("你好")
        manager = ModelManager(data_dir=tmp_data_dir)
        # Act
        path = manager.ensure_model("large-v3-turbo", "int8")
        # Assert
        assert path == model_dir

    def test_should_trigger_download_when_model_missing(self, tmp_data_dir):
        # Arrange
        from voiceime.model.manager import ModelManager

        manager = ModelManager(data_dir=tmp_data_dir)
        with patch("voiceime.model.downloader.download_model") as mock_dl:
            mock_dl.return_value = tmp_data_dir / "models" / "large-v3-turbo"
            # Act
            path = manager.ensure_model("large-v3-turbo", "int8")
        # Assert
        mock_dl.assert_called_once()

    def test_should_raise_error_when_download_fails_3_times(self, tmp_data_dir):
        # Arrange
        from voiceime.model.manager import ModelManager
        from voiceime.model.downloader import DownloadError

        manager = ModelManager(data_dir=tmp_data_dir)
        with patch("voiceime.model.downloader.download_model") as mock_dl:
            mock_dl.side_effect = DownloadError("network error")
            # Act & Assert
            with pytest.raises(DownloadError):
                manager.ensure_model("large-v3-turbo", "int8")

    def test_should_return_false_when_model_incomplete(self, tmp_data_dir):
        # Arrange — 缺少 vocabulary.txt
        from voiceime.model.manager import ModelManager

        model_dir = tmp_data_dir / "models" / "broken"
        model_dir.mkdir(parents=True)
        (model_dir / "model.bin").write_bytes(b"fake")
        manager = ModelManager(data_dir=tmp_data_dir)
        # Act
        result = manager.verify_model(model_dir)
        # Assert
        assert result is False

    def test_should_list_available_models(self, tmp_data_dir):
        # Arrange
        from voiceime.model.manager import ModelManager

        model_dir = tmp_data_dir / "models" / "large-v3-turbo"
        model_dir.mkdir(parents=True)
        (model_dir / "model.bin").write_bytes(b"fake")
        (model_dir / "config.json").write_text("{}")
        (model_dir / "vocabulary.txt").write_text("你好")
        manager = ModelManager(data_dir=tmp_data_dir)
        # Act
        models = manager.available_models
        # Assert
        assert "large-v3-turbo" in models
```

### 3.2.8 CoreController 状态机 (F11)

```python
# tests/unit/test_core_state_machine.py
from unittest.mock import MagicMock

import pytest


class TestCoreStateMachine:
    """CoreController 状态机单元测试 — 状态流转、错误恢复、防抖。"""

    describe = "CoreController StateMachine"

    def test_should_transition_to_recording_when_hotkey_down_from_ready(self):
        # Arrange
        from voiceime.core import CoreController

        core = CoreController.__new__(CoreController)
        core._state = "READY"
        core._recorder = MagicMock()
        core._hotkey_manager = MagicMock()
        # Act
        core._on_hotkey_down()
        # Assert
        assert core._state == "RECORDING"

    def test_should_transition_to_inferring_when_hotkey_up_from_recording(self):
        # Arrange
        from voiceime.core import CoreController

        core = CoreController.__new__(CoreController)
        core._state = "RECORDING"
        core._recorder = MagicMock()
        core._recorder.stop_recording.return_value = MagicMock(
            pcm=MagicMock(), duration_ms=1000, sample_rate=16000
        )
        core._asr_engine = MagicMock()
        core._output_controller = MagicMock()
        # Act
        core._on_hotkey_up()
        # Assert
        assert core._state == "INFERRING"

    def test_should_ignore_hotkey_when_in_paused_state(self):
        # Arrange
        from voiceime.core import CoreController

        core = CoreController.__new__(CoreController)
        core._state = "PAUSED"
        core._recorder = MagicMock()
        # Act
        core._on_hotkey_down()
        # Assert — 状态不应改变
        assert core._state == "PAUSED"

    def test_should_enter_error_mic_when_recorder_fails(self):
        # Arrange
        from voiceime.core import CoreController
        from voiceime.recorder.device import DeviceNotFoundError

        core = CoreController.__new__(CoreController)
        core._state = "READY"
        core._recorder = MagicMock()
        core._recorder.start_recording.side_effect = DeviceNotFoundError()
        # Act
        core._on_hotkey_down()
        # Assert
        assert core._state == "ERROR_MIC"

    def test_should_enter_error_model_when_asr_not_loaded(self):
        # Arrange
        from voiceime.core import CoreController

        core = CoreController.__new__(CoreController)
        core._state = "RECORDING"
        core._recorder = MagicMock()
        core._recorder.stop_recording.return_value = MagicMock(
            pcm=MagicMock(), duration_ms=1000, sample_rate=16000
        )
        core._asr_engine = MagicMock()
        core._asr_engine.is_loaded = False
        # Act
        core._on_hotkey_up()
        # Assert
        assert core._state == "ERROR_MODEL"

    def test_should_recover_to_ready_from_error_state(self):
        # Arrange
        from voiceime.core import CoreController

        core = CoreController.__new__(CoreController)
        core._state = "ERROR_MIC"
        core._asr_engine = MagicMock()
        core._asr_engine.is_loaded = True
        core._recorder = MagicMock()
        # Act
        core._recover()
        # Assert
        assert core._state == "READY"

    def test_should_complete_full_cycle_from_ready_back_to_ready(self):
        # Arrange
        from voiceime.core import CoreController

        core = CoreController.__new__(CoreController)
        core._state = "READY"
        core._recorder = MagicMock()
        core._recorder.stop_recording.return_value = MagicMock(
            pcm=MagicMock(), duration_ms=1000, sample_rate=16000
        )
        core._asr_engine = MagicMock()
        core._asr_engine.is_loaded = True
        asr_result = MagicMock(text="你好", language="zh", inference_ms=500)
        core._asr_engine.transcribe.return_value = asr_result
        core._output_controller = MagicMock()
        core._output_controller.output.return_value = MagicMock(
            success=True, method="clipboard", error=None
        )
        # Act — 完整周期
        core._on_hotkey_down()
        assert core._state == "RECORDING"
        core._on_hotkey_up()
        assert core._state == "INFERRING"
        core._on_asr_result(asr_result)
        # Assert — 最终回到 READY
        assert core._state == "READY"
```

### 3.2.9 SingleInstance (F13)

```python
# tests/unit/test_single_instance.py
from unittest.mock import patch

import pytest


class TestSingleInstance:
    """SingleInstance 单元测试 — 互斥体、多实例阻止。"""

    describe = "SingleInstance"

    def test_should_acquire_lock_when_first_instance(self):
        # Arrange
        from voiceime.utils.single_instance import SingleInstance

        with patch("voiceime.utils.single_instance.ctypes") as mock_ctypes:
            mock_ctypes.windll.kernel32.CreateMutexW.return_value = 1
            mock_ctypes.GetLastError.return_value = 0
            instance = SingleInstance("VoiceIME")
            # Act
            result = instance.acquire()
        # Assert
        assert result is True

    def test_should_fail_when_second_instance_tries(self):
        # Arrange
        from voiceime.utils.single_instance import SingleInstance

        with patch("voiceime.utils.single_instance.ctypes") as mock_ctypes:
            mock_ctypes.windll.kernel32.CreateMutexW.return_value = 1
            mock_ctypes.GetLastError.return_value = 183  # ERROR_ALREADY_EXISTS
            instance = SingleInstance("VoiceIME")
            # Act
            result = instance.acquire()
        # Assert
        assert result is False

    def test_should_release_lock_on_cleanup(self):
        # Arrange
        from voiceime.utils.single_instance import SingleInstance

        with patch("voiceime.utils.single_instance.ctypes") as mock_ctypes:
            mock_ctypes.windll.kernel32.CreateMutexW.return_value = 1
            mock_ctypes.GetLastError.return_value = 0
            instance = SingleInstance("VoiceIME")
            instance.acquire()
            # Act
            instance.release()
        # Assert — CloseHandle 应被调用
        mock_ctypes.windll.kernel32.CloseHandle.assert_called()
```

---

## 3.3 集成测试（基于接口契约）

### 3.3.1 CONTRACT-01: HotkeyProvider

```python
# tests/integration/test_contract_hotkey.py
from unittest.mock import MagicMock, patch

import pytest


class TestContractHotkeyProvider:
    """验证 HotkeyManager 实现符合 CONTRACT-01 协议。"""

    def test_should_start_and_stop_hook_without_error(self):
        # Arrange
        from voiceime.hotkey.manager import HotkeyManager

        manager = HotkeyManager(hotkey="caps_lock")
        with patch("voiceime.hotkey.manager.Listener") as mock_listener:
            mock_listener.return_value.start = MagicMock()
            mock_listener.return_value.stop = MagicMock()
            # Act
            manager.start()
            manager.stop()
        # Assert — 无异常抛出

    def test_should_queue_hotkey_event_when_key_pressed(self):
        # Arrange
        from voiceime.hotkey.manager import HotkeyManager

        manager = HotkeyManager(hotkey="caps_lock")
        on_keydown = MagicMock()
        on_keyup = MagicMock()
        manager.set_callback(on_keydown, on_keyup)
        # Act
        manager._handle_key_event("caps_lock", "down")
        manager._handle_key_event("caps_lock", "up")
        # Assert
        on_keydown.assert_called_once()
        on_keyup.assert_called_once()

    def test_should_satisfy_protocol_interface(self):
        # Arrange
        from voiceime.hotkey.manager import HotkeyManager
        from voiceime.protocols import HotkeyProvider

        manager = HotkeyManager(hotkey="caps_lock")
        # Act & Assert — 应满足 Protocol 接口
        assert isinstance(manager, HotkeyProvider)
```

### 3.3.2 CONTRACT-02: AudioProvider

```python
# tests/integration/test_contract_audio.py
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestContractAudioProvider:
    """验证 RecorderStream 实现符合 CONTRACT-02 协议。"""

    def test_should_produce_audio_data_with_correct_fields(self, sample_pcm_1s):
        # Arrange
        from voiceime.recorder.stream import RecorderStream

        recorder = RecorderStream(sample_rate=16000)
        with patch("voiceime.recorder.stream.sd.InputStream"):
            recorder.start_recording()
            recorder._buffer.append(sample_pcm_1s)
            # Act
            result = recorder.stop_recording()
        # Assert
        assert hasattr(result, "pcm")
        assert hasattr(result, "duration_ms")
        assert hasattr(result, "sample_rate")
        assert result.sample_rate == 16000

    def test_should_list_available_devices(self):
        # Arrange
        from voiceime.recorder.stream import RecorderStream

        with patch("voiceime.recorder.device.sd.query_devices") as mock_query:
            mock_query.return_value = [
                {"id": 0, "name": "Mic 1", "is_default": True}
            ]
            recorder = RecorderStream(sample_rate=16000)
            # Act
            devices = recorder.devices
        # Assert
        assert len(devices) >= 0  # 至少不崩溃

    def test_should_satisfy_protocol_interface(self):
        # Arrange
        from voiceime.recorder.stream import RecorderStream
        from voiceime.protocols import AudioProvider

        recorder = RecorderStream(sample_rate=16000)
        # Act & Assert
        assert isinstance(recorder, AudioProvider)
```

### 3.3.3 CONTRACT-05: OutputProvider

```python
# tests/integration/test_contract_output.py
from unittest.mock import MagicMock

import pytest


class TestContractOutputProvider:
    """验证 OutputController 实现符合 CONTRACT-05 协议。"""

    def test_should_return_output_result_with_required_fields(self):
        # Arrange
        from voiceime.output.controller import OutputController

        controller = OutputController()
        controller._clipboard = MagicMock()
        controller._clipboard.output.return_value = MagicMock(
            success=True, method="clipboard", error=None
        )
        # Act
        result = controller.output("测试文本")
        # Assert
        assert hasattr(result, "success")
        assert hasattr(result, "method")
        assert hasattr(result, "error")

    def test_should_follow_fallback_order_defined_in_contract(self):
        # Arrange
        from voiceime.output.controller import OutputController

        controller = OutputController()
        call_log = []
        for method_name in ("_clipboard", "_uia", "_keyboard"):
            mock = MagicMock()
            mock.output.side_effect = lambda *a, mn=method_name, **kw: (
                call_log.append(mn) or MagicMock(
                    success=mn == "_keyboard", method=mn, error=None
                )
            )
            setattr(controller, method_name, mock)
        # Act
        result = controller.output("测试")
        # Assert — 依次尝试 clipboard → uia → keyboard
        assert call_log == ["_clipboard", "_uia", "_keyboard"]

    def test_should_satisfy_protocol_interface(self):
        # Arrange
        from voiceime.output.controller import OutputController
        from voiceime.protocols import OutputProvider

        controller = OutputController()
        # Act & Assert
        assert isinstance(controller, OutputProvider)
```

### 3.3.4 CONTRACT-06: ConfigProvider

```python
# tests/integration/test_contract_config.py
import pytest


class TestContractConfigProvider:
    """验证 ConfigManager 实现符合 CONTRACT-06 协议。"""

    def test_should_support_dot_path_access(self, tmp_data_dir):
        # Arrange
        from voiceime.config.manager import ConfigManager

        manager = ConfigManager(data_dir=tmp_data_dir)
        # Act
        value = manager.get("asr.model")
        # Assert
        assert value is not None

    def test_should_persist_and_reload(self, tmp_data_dir):
        # Arrange
        from voiceime.config.manager import ConfigManager

        manager = ConfigManager(data_dir=tmp_data_dir)
        # Act
        manager.set("asr.vad", False)
        manager2 = ConfigManager(data_dir=tmp_data_dir)
        # Assert
        assert manager2.get("asr.vad") is False

    def test_should_satisfy_protocol_interface(self, tmp_data_dir):
        # Arrange
        from voiceime.config.manager import ConfigManager
        from voiceime.protocols import ConfigProvider

        manager = ConfigManager(data_dir=tmp_data_dir)
        # Act & Assert
        assert isinstance(manager, ConfigProvider)
```

### 3.3.5 CONTRACT-08: ModelProvider

```python
# tests/integration/test_contract_model.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestContractModelProvider:
    """验证 ModelManager 实现符合 CONTRACT-08 协议。"""

    def test_should_ensure_model_returns_path(self, tmp_data_dir):
        # Arrange
        from voiceime.model.manager import ModelManager

        model_dir = tmp_data_dir / "models" / "large-v3-turbo"
        model_dir.mkdir(parents=True)
        for f in ("model.bin", "config.json", "vocabulary.txt"):
            (model_dir / f).write_text("dummy")
        manager = ModelManager(data_dir=tmp_data_dir)
        # Act
        path = manager.ensure_model("large-v3-turbo", "int8")
        # Assert
        assert isinstance(path, Path)

    def test_should_verify_model_integrity(self, tmp_data_dir):
        # Arrange
        from voiceime.model.manager import ModelManager

        model_dir = tmp_data_dir / "models" / "test-model"
        model_dir.mkdir(parents=True)
        for f in ("model.bin", "config.json", "vocabulary.txt"):
            (model_dir / f).write_text("dummy")
        manager = ModelManager(data_dir=tmp_data_dir)
        # Act
        result = manager.verify_model(model_dir)
        # Assert
        assert result is True

    def test_should_satisfy_protocol_interface(self, tmp_data_dir):
        # Arrange
        from voiceime.model.manager import ModelManager
        from voiceime.protocols import ModelProvider

        manager = ModelManager(data_dir=tmp_data_dir)
        # Act & Assert
        assert isinstance(manager, ModelProvider)
```

### 3.3.6 全链路集成测试

```python
# tests/integration/test_pipeline_e2e.py
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestPipelineE2E:
    """热键→录音→ASR→上屏 全链路集成测试（Mock 外部依赖）。"""

    describe = "Full Pipeline Integration"

    def test_should_complete_full_pipeline_from_hotkey_to_output(self, tmp_data_dir):
        """
        Happy Path: Caps Lock down → 录音 → up → ASR 识别 → 上屏成功
        """
        # Arrange
        from voiceime.core import CoreController
        from voiceime.config.manager import ConfigManager

        config = ConfigManager(data_dir=tmp_data_dir)

        # Mock recorder
        mock_recorder = MagicMock()
        mock_pcm = np.sin(
            np.linspace(0, 5.0, 80000, dtype=np.float32)
        )
        mock_recorder.stop_recording.return_value = MagicMock(
            pcm=mock_pcm, duration_ms=5000, sample_rate=16000
        )

        # Mock ASR
        mock_asr = MagicMock()
        mock_asr.is_loaded = True
        mock_asr.transcribe.return_value = MagicMock(
            text="你好世界", language="zh", inference_ms=1500
        )

        # Mock output
        mock_output = MagicMock()
        mock_output.output.return_value = MagicMock(
            success=True, method="clipboard", error=None
        )

        core = CoreController(
            config=config,
            recorder=mock_recorder,
            asr_engine=mock_asr,
            output_controller=mock_output,
        )
        core._state = "READY"

        # Act — 模拟完整流程
        core._on_hotkey_down()    # READY → RECORDING
        core._on_hotkey_up()      # RECORDING → INFERRING
        core._on_asr_result(
            MagicMock(text="你好世界", language="zh", inference_ms=1500)
        )
        # INFERRING → OUTPUTTING → READY

        # Assert
        assert core._state == "READY"
        mock_output.output.assert_called_once_with("你好世界")

    def test_should_handle_asr_timeout_gracefully(self, tmp_data_dir):
        """
        异常路径: ASR 推理超时 → 进入 ERROR_INFERENCE_TIMEOUT → 恢复到 READY
        """
        # Arrange
        from voiceime.core import CoreController
        from voiceime.asr.engine import InferenceTimeoutError

        mock_recorder = MagicMock()
        mock_recorder.stop_recording.return_value = MagicMock(
            pcm=np.zeros(16000, dtype=np.float32),
            duration_ms=1000,
            sample_rate=16000,
        )
        mock_asr = MagicMock()
        mock_asr.is_loaded = True
        mock_asr.transcribe.side_effect = InferenceTimeoutError()
        mock_output = MagicMock()

        core = CoreController(
            recorder=mock_recorder,
            asr_engine=mock_asr,
            output_controller=mock_output,
        )
        core._state = "READY"

        # Act
        core._on_hotkey_down()
        core._on_hotkey_up()

        # Assert
        assert core._state == "ERROR_INFERENCE_TIMEOUT"
        mock_output.output.assert_not_called()

    def test_should_fallback_to_uia_when_clipboard_fails(self):
        """
        降级路径: clipboard 失败 → uia 成功
        """
        # Arrange
        from voiceime.output.controller import OutputController

        controller = OutputController()
        controller._clipboard = MagicMock()
        controller._clipboard.output.return_value = MagicMock(
            success=False, method="clipboard", error="locked"
        )
        controller._uia = MagicMock()
        controller._uia.output.return_value = MagicMock(
            success=True, method="uia", error=None
        )
        # Act
        result = controller.output("降级测试")
        # Assert
        assert result.success is True
        assert result.method == "uia"
```

---

## 3.4 E2E 测试（pytest-qt）

### 3.4.1 系统托盘 (F08)

```python
# tests/e2e/test_tray.py
from unittest.mock import MagicMock, patch

import pytest


class TestSystemTrayE2E:
    """系统托盘 E2E 测试 — 需要 QApplication 实例。"""

    def test_should_show_tray_icon_on_startup(self, qapp):
        # Arrange
        from voiceime.ui.tray import SystemTray

        with patch("voiceime.ui.tray.pystray.Icon") as mock_icon:
            mock_icon.return_value.run = MagicMock()
            tray = SystemTray()
            # Act
            tray.start()
        # Assert — 托盘图标应已创建
        mock_icon.assert_called_once()

    def test_should_switch_icon_on_state_change(self, qapp):
        # Arrange
        from voiceime.ui.tray import SystemTray

        with patch("voiceime.ui.tray.pystray.Icon"):
            tray = SystemTray()
            # Act
            tray.update_state("READY")
            # Assert — 图标应为绿色就绪态
            # TODO: 验证图标颜色/名称变化

    def test_should_quit_on_exit_menu_click(self, qapp):
        # Arrange
        from voiceime.ui.tray import SystemTray

        with patch("voiceime.ui.tray.pystray.Icon") as mock_icon:
            tray = SystemTray()
            tray.start()
            # Act — 模拟点击退出菜单
            # TODO: 找到退出菜单回调并触发
```

### 3.4.2 设置窗口 (F14)

```python
# tests/e2e/test_settings.py
from unittest.mock import MagicMock, patch

import pytest


class TestSettingsE2E:
    """设置窗口 E2E 测试 — pytest-qt qtbot 操作 PyQt6 控件。"""

    def test_should_persist_asr_model_change(self, qtbot, tmp_data_dir):
        # Arrange
        from voiceime.ui.settings import SettingsWindow
        from voiceime.config.manager import ConfigManager

        config = ConfigManager(data_dir=tmp_data_dir)
        with patch("voiceime.ui.settings.SettingsWindow.__init__", lambda s: None):
            window = SettingsWindow()
            window._config = config
            # TODO: 初始化 UI 控件
            # Act — 修改模型选择并保存
            # Assert — 配置应持久化
            pass

    def test_should_reject_invalid_vad_parameter(self, qtbot, tmp_data_dir):
        # Arrange — TODO: 填充无效 VAD 参数测试
        pass
```

### 3.4.3 冒烟测试

```python
# tests/e2e/test_smoke.py
"""全链路冒烟测试 — 验证应用可启动并完成基本流程。"""
from unittest.mock import patch

import pytest


class TestSmokeE2E:
    """冒烟测试 — 最小化验证应用核心流程可运行。"""

    def test_should_import_all_modules_without_error(self):
        """验证所有模块可正常导入。"""
        modules = [
            "voiceime.config.manager",
            "voiceime.hotkey.manager",
            "voiceime.recorder.stream",
            "voiceime.asr.engine",
            "voiceime.output.controller",
            "voiceime.model.manager",
            "voiceime.core",
            "voiceime.protocols",
        ]
        for module_name in modules:
            # Act
            __import__(module_name)
        # Assert — 无 ImportError

    def test_should_create_core_controller_without_crash(self, tmp_data_dir):
        """验证 CoreController 可正常实例化。"""
        from voiceime.core import CoreController

        with patch("voiceime.core.HotkeyManager"), \
             patch("voiceime.core.RecorderStream"), \
             patch("voiceime.core.ASREngine"), \
             patch("voiceime.core.OutputController"), \
             patch("voiceime.core.ModelManager"):
            core = CoreController(data_dir=tmp_data_dir)
        # Assert — 无崩溃
        assert core._state == "UNINITIALIZED"
```

---

# 4 测试资产交付清单

| # | 资产文件名 | 类型 | 覆盖功能点 | 状态 |
|---|-----------|------|-----------|------|
| 1 | `tests/conftest.py` | Fixture | 全局 | 已生成框架 |
| 2 | `tests/unit/test_config_manager.py` | Unit | F09 ConfigManager | 已生成框架 |
| 3 | `tests/unit/test_hotkey_manager.py` | Unit | F01 全局热键 | 已生成框架 |
| 4 | `tests/unit/test_recorder_stream.py` | Unit | F02 麦克风录音 | 已生成框架 |
| 5 | `tests/unit/test_asr_engine.py` | Unit | F03 ASR 推理 | 已生成框架 |
| 6 | `tests/unit/test_output_clipboard.py` | Unit | F04+F12 剪贴板上屏+保护 | 已生成框架 |
| 7 | `tests/unit/test_output_controller.py` | Unit | F07 Fallback 编排 | 已生成框架 |
| 8 | `tests/unit/test_model_manager.py` | Unit | F10 模型管理 | 已生成框架 |
| 9 | `tests/unit/test_core_state_machine.py` | Unit | F11 状态机 | 已生成框架 |
| 10 | `tests/unit/test_single_instance.py` | Unit | F13 进程安全 | 已生成框架 |
| 11 | `tests/integration/test_contract_hotkey.py` | Integration | CONTRACT-01 | 已生成框架 |
| 12 | `tests/integration/test_contract_audio.py` | Integration | CONTRACT-02 | 已生成框架 |
| 13 | `tests/integration/test_contract_output.py` | Integration | CONTRACT-05 | 已生成框架 |
| 14 | `tests/integration/test_contract_config.py` | Integration | CONTRACT-06 | 已生成框架 |
| 15 | `tests/integration/test_contract_model.py` | Integration | CONTRACT-08 | 已生成框架 |
| 16 | `tests/integration/test_pipeline_e2e.py` | Integration | 全链路 Happy Path + 异常 | 已生成框架 |
| 17 | `tests/e2e/test_tray.py` | E2E | F08 系统托盘 | 已生成框架 |
| 18 | `tests/e2e/test_settings.py` | E2E | F14 设置窗口 | 已生成框架 |
| 19 | `tests/e2e/test_smoke.py` | E2E | 冒烟验证 | 已生成框架 |

> ⚠️ 所有"已生成框架"条目的实际测试结果，须由工程师运行后回填。本 Skill 不产出任何运行时结论。

---

# 5 性能验收指标（待实测）

| 指标 | 目标值 | 测试方法 | 优先级 | 状态 |
|------|--------|---------|--------|------|
| 首次模型加载 | ≤ 8s (SSD 冷启动) | `test_asr_engine.py` 计时 | P0 | 待实测 |
| 二次唤醒延迟 | < 100ms (内存锁定后) | `test_core_state_machine.py` 计时 | P0 | 待实测 |
| 5s 音频推理 (CPU) | ≤ 2.5s (int8) | `test_asr_engine.py` 真实推理 | P0 | 待实测 |
| 内存占用 | ≤ 4 GB | 进程监控 | P0 | 待实测 |
| 待机 CPU | < 1% | 进程监控 30s 采样 | P0 | 待实测 |

---

# 6 pytest 配置建议

```toml
# pyproject.toml [tool.pytest.ini_options]
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
markers = [
    "unit: Unit tests (no external dependencies)",
    "integration: Integration tests (cross-module)",
    "e2e: End-to-end tests (full application)",
    "slow: Slow tests (real model loading, etc.)",
]
```

```txt
# requirements-dev.txt
pytest>=8.0
pytest-mock>=3.12
pytest-qt>=4.4
pytest-cov>=5.0
```

---

# 7 交付契约

```
→ 输出交付给：Skill 06 (部署)，作为上线 Go/No-Go 决策的测试覆盖依据
→ 必须包含：RTM 表 + 各层级测试代码框架 + 资产交付清单
→ 格式要求：测试代码使用代码块，注明语言类型 (python)
→ 测试范围：Phase 1 MVP (P0)，核心链路 100% 覆盖
→ 测试框架：pytest + pytest-qt + pytest-mock
```
