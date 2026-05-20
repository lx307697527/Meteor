# VoiceIME DevOrchestration Digest

> Source: docs/engineering/DevOrchestration.md | Version: pending | Synced: —
> 开发编排文档尚未创建。本 digest 将在 DevOrchestration.md 完成后同步填充。

## 状态

等待 Skill 04 (开发编排) 输出后创建源文档并同步。

## PRD 中已定义的里程碑（预填）

| 阶段 | 周期 | 核心交付 |
|------|------|---------|
| Phase 1 MVP | 1-2 周 | 热键录音 + VAD + faster-whisper CPU + 剪贴板上屏 + 托盘图标 + 基础设置 |
| Phase 2 体验 | 2-3 周 | 悬浮条 UI + 热词词库 + 历史记录 + 繁简转换 + LLM 润色 + 内存锁定 |
| Phase 3 智能 | 1-2 周 | Vulkan 加速评估 + 上下文感知规则引擎 + 远程推理 API |

## Phase 1 关键任务（来自 PRD §5.1）

| 任务 | 技术要点 | 优先级 |
|------|---------|--------|
| 全局键盘钩子 | pynput, Caps Lock 拦截, 防止系统默认行为 | P0 |
| 麦克风录音模块 | sounddevice, 16kHz/Mono, numpy buffer, 动态设备切换 | P0 |
| VAD 集成 | faster-whisper 内置, vad_filter=True, min_silence=300ms | P0 |
| faster-whisper 推理 | large-v3-turbo, int8, CPU, 模型常驻内存 | P0 |
| 剪贴板上屏 | pyperclip+pyautogui, 备份→写入→Ctrl+V→50ms→恢复 | P0 |
| 系统托盘 | pystray, 状态图标切换, 右键菜单, 双击打开设置 | P0 |
| 配置文件读写 | JSON, %APPDATA%\VoiceIME\config.json | P0 |
