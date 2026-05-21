# VoiceIME DevOrchestration Digest

> Source: docs/engineering/DevOrchestration.md | Version: V1.0 | Synced: 2026-05-21
> 开发编排文档的压缩摘要。里程碑细节、接口契约、Agent 任务分配请查阅源文档。

## 开发模式

2 Agent 并行 + 灵活周期（按 PRD Phase 推进）。

## Agent 分工

| Agent | 职责 | 文件范围 |
|-------|------|---------|
| infra-agent (A) | 骨架、Config、Model、全部 UI、Keyring、History、Hotword、打包 | utils/, config/, keyring/, hotword/, history/, model/, ui/, __main__.py |
| pipeline-agent (B) | 热键、录音、ASR、后处理、上屏、LLM、CoreController、Context | hotkey/, recorder/, asr/, postprocess/, output/, llm/, context/, core.py |

## 唯一共享文件

`voiceime/protocols.py` — 全部 Protocol 接口定义，修改需双方确认。

## 关键路径

```
config → model → asr → core → output
```

## Phase 1 MVP（1-2 周 / M1.1-M1.11）

| 里程碑 | 核心交付 | Agent |
|--------|---------|-------|
| M1.1 骨架 | 目录结构 + 入口可运行 | A+B |
| M1.2 基础设施 | ConfigManager + utils | A |
| M1.3 模型管理 | ModelManager + HuggingFace 下载 | A |
| M1.4 热键+录音 | HotkeyManager + Recorder | B |
| M1.5 ASR 推理 | ASREngine (faster-whisper) | B |
| M1.6 文本上屏 | OutputController (三层 Fallback) | B |
| M1.7 系统托盘 | SystemTray (pystray) | A |
| M1.8 集成联调 | CoreController 串联全链路 | B |
| M1.9 首次引导 | FirstRunWizard | A |
| M1.10 基础设置 | SettingsWindow 推理 Tab | A |
| M1.11 MVP 打包 | PyInstaller 单文件 | A+B |

## Phase 2 体验（2-3 周 / M2.1-M2.8）

| 里程碑 | 核心交付 | Agent |
|--------|---------|-------|
| M2.1 悬浮条 UI | FloatingBar + 波形 | A |
| M2.2 后处理 | Pipeline (标点+繁简+热词) | B |
| M2.3 LLM 集成 | LLMClient + KeyringStore | A+B |
| M2.4 历史记录 | HistoryRepo + HistoryWindow | A |
| M2.5 热词词库 | HotwordRepo + HotwordWindow | A |
| M2.6 完整设置 | Settings 5 Tab | A |
| M2.7 内存锁定 | VirtualLock + 心跳 | B |
| M2.8 Phase 2 集成 | 全部 P1 联调 | A+B |

## Phase 3 智能化（1-2 周 / M3.1-M3.4）

| 里程碑 | 核心交付 | Agent |
|--------|---------|-------|
| M3.1 Vulkan 评估 | whisper.cpp benchmark | B |
| M3.2 上下文感知 | ContextEngine + 规则匹配 | A+B |
| M3.3 性能验收 | 全量性能测试 | B |
| M3.4 最终发布 | 打包 + 用户文档 | A+B |

## 接口契约（10 个）

CONTRACT-01~10：HotkeyProvider, AudioProvider, ASRProvider, PostProcessProvider, OutputProvider, ConfigProvider, HistoryProvider, ModelProvider, LLMProvider, StateMachine。详见源文档 §2。

## 最大风险

CPU 推理性能待实测（M1.5 完成后立即验证 5s ≤ 2.5s 目标）。
