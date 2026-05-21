# VoiceIME TestPlan Digest

> Source: docs/qa/TestPlan.md | Version: V1.0 | Synced: 2026-05-21
> 测试计划的压缩摘要。测试用例详细代码请查阅源文档。

## 测试框架

- 单元/集成：pytest + pytest-mock
- E2E：pytest-qt（PyQt6 控件操作）
- 覆盖范围：Phase 1 MVP，核心链路 100%

## 测试分层

| 层级 | 文件数 | 覆盖 |
|------|--------|------|
| Unit | 10 文件 | ConfigManager / HotkeyManager / Recorder / ASR / Output三层 / ModelManager / CoreController状态机 / SingleInstance |
| Integration | 6 文件 | CONTRACT-01/02/05/06/08 + 全链路管道 |
| E2E | 3 文件 | 系统托盘 / 设置窗口 / 冒烟测试 |

## 需求跟踪矩阵（14 个功能点 × 3 类用例）

每个 P0 功能点至少覆盖：1 正常 + 1 边缘 + 1 异常用例。

核心覆盖：
- F01 热键：按下/松开回调、冲突、非目标键过滤
- F02 录音：PCM 输出、60s 截断、200ms 最短、设备断开
- F03 ASR：推理返回、超时 30s、模型未加载、VAD 静音
- F04+F12 剪贴板：备份恢复、原内容为空、写入失败
- F07 Fallback：clipboard→uia→keyboard 三层降级
- F11 状态机：完整 READY→RECORDING→INFERRING→OUTPUTTING→READY 周期 + 错误态恢复

## Mock 策略

faster-whisper / sounddevice / pynput / pystray / pyautogui / keyring / UIAutomation / HuggingFace 下载 / Windows API 均通过 `unittest.mock` 隔离。

## 性能验收指标

| 指标 | 目标 | 测试位置 | 状态 |
|------|------|---------|------|
| 首次模型加载 | ≤ 8s | test_asr_engine.py | 待实测 |
| 二次唤醒 | < 100ms | test_core_state_machine.py | 待实测 |
| 5s 音频推理 CPU | ≤ 2.5s | test_asr_engine.py | 待实测 |
| 内存占用 | ≤ 4 GB | 进程监控 | 待实测 |
| 待机 CPU | < 1% | 进程监控 | 待实测 |

## 关键风险

- CPU 推理性能目标（5s≤2.5s）需真实模型实测验证
- pytest-qt 需要 QApplication 实例，CI 环境需虚拟显示或 headless 配置
