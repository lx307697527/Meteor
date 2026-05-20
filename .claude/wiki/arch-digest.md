# VoiceIME Architecture Digest

> Source: docs/architecture/Architecture.md | Version: pending | Synced: —
> 架构文档尚未创建。本 digest 将在 Architecture.md 完成后同步填充。

## 状态

等待 Skill 03 (架构设计) 输出后创建源文档并同步。

## PRD 中已定义的架构约束（预填）

### 四层架构（来自 PRD §6.2）

| 层 | 组件 |
|----|------|
| **用户交互层** | 系统托盘图标 · 悬浮录音条 · 设置窗口 · 热词词库窗口 · 历史记录窗口 |
| **核心控制层** | HotkeyListener(pynput) → Recorder(sounddevice) → VAD(Silero) → Engine(faster-whisper) |
| **后处理层** | 标点规范化 → 繁简转换(OpenCC) → 热词替换 → LLM润色(可选) |
| **输出层** | UIAutomation / 剪贴板+Ctrl+V / 逐字符输入 |

### 持久化

| 文件 | 用途 | 格式 |
|------|------|------|
| config.json | 全局配置 | JSON (%APPDATA%\VoiceIME\) |
| history.sqlite | 历史记录 | SQLite |
| hotwords.json | 热词词库 | JSON |

### 技术栈（来自 PRD §6.1）

| 模块 | 选型 |
|------|------|
| 全局热键 | pynput |
| 音频录制 | sounddevice + numpy |
| VAD | faster-whisper 内置 Silero |
| ASR | faster-whisper (CTranslate2) / whisper.cpp (Phase 2) |
| 文本上屏 | pyperclip + pyautogui / pywinauto |
| 系统托盘 | pystray |
| 设置窗口 | PyQt6 或 tkinter |
| LLM 调用 | anthropic / openai SDK |
| 繁简转换 | opencc-python-reimplemented |
| 配置存储 | JSON |
| 历史记录 | SQLite (sqlite3) |
| API Key | keyring (Windows Credential Manager) |
