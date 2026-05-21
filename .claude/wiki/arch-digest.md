# VoiceIME Architecture Digest

> Source: docs/architecture/Architecture.md | Version: V1.0 | Synced: 2026-05-21

## 架构模式

模块化单体（Modular Monolith），单进程 5 线程，queue.Queue + QTimer 50ms 轮询通信。

## 四层架构

| 层 | 组件 |
|----|------|
| **用户交互层 (UI)** | SystemTray(pystray) · FloatingBar(PyQt6) · SettingsWindow · HotwordWindow · HistoryWindow · FirstRunWizard |
| **核心控制层 (Core)** | HotkeyManager → Recorder → ASREngine → PostProcessPipeline → OutputController |
| **基础设施层 (Infra)** | ConfigManager · HistoryRepo · ModelManager · KeyringStore · ContextEngine(P2) · ClipboardGuard |
| **输出层 (Output)** | ClipboardGuard(主) / UIAOutput(辅助) / KeyboardOutput(兜底) |

## 线程模型

| 线程 | 框架 | 职责 |
|------|------|------|
| 主线程 | PyQt6 QApplication | CoreController 状态机、UI、后处理编排、上屏、QTimer 消费队列 |
| 托盘线程 | pystray | 系统托盘图标 + 右键菜单，cmd_queue 通知主线程 |
| 热键线程 | pynput Listener | WH_KEYBOARD_LL，hotkey_queue 通知主线程 |
| 音频线程 | sounddevice 回调 | PCM 采集写入 ring buffer，零阻塞 |
| 推理线程 | ThreadPoolExecutor(1) | faster-whisper CPU 推理，result_queue 回传 |
| LLM 线程 | ThreadPoolExecutor(1) | LLM API HTTP 调用，llm_queue 回传 |

## 全局状态机

UNINITIALIZED → READY ⇄ RECORDING → INFERRING → CONFIRMING → OUTPUTTING → READY
异常态：ERROR_MIC / ERROR_MODEL / ERROR_INFERENCE_TIMEOUT / ERROR_LLM_TIMEOUT / ERROR_CLIPBOARD

## 核心数据模型

| 文件 | 用途 | 路径 |
|------|------|------|
| config.json | 全局配置 | %APPDATA%\VoiceIME\config.json |
| history.sqlite | 识别历史 | %APPDATA%\VoiceIME\history.sqlite |
| hotwords.json | 热词映射 | %APPDATA%\VoiceIME\hotwords.json |
| context_rules.json | 上下文规则(P2) | %APPDATA%\VoiceIME\context_rules.json |

## 关键技术栈

| 层级 | 选型 | 放弃方案 |
|------|------|---------|
| UI | PyQt6 | tkinter(控件少) |
| 托盘 | pystray | QSystemTrayIcon(耦合主循环) |
| 热键 | pynput | ctypes WH_KEYBOARD_LL(成本高) |
| 音频 | sounddevice+numpy | pyaudio(编译问题) |
| ASR | faster-whisper(CTranslate2) | whisper.cpp(Vulkan待验证) |
| 繁简 | opencc-python-reimplemented | opencc(需C++编译) |
| API Key | keyring→Windows Credential Manager | 自定义加密 |
| 打包 | PyInstaller | Nuitka(构建复杂) |

## 韧性方案要点

- 剪贴板：备份→写入→Ctrl+V→延迟恢复，失败降级逐字符
- 配置容灾：损坏→.bak→新建默认
- 模型容灾：加载失败→降级模式（仅托盘，ASR禁用）
- 进程安全：atexit+try/finally+Windows自动卸载DLL+命名互斥体防多实例
- LLM：超时10s/DNS 5s，失败保留原文

## 最大风险点

CPU 推理性能（5s音频≤2.5s目标待实测），不达标需切Vulkan后端或降级模型。
