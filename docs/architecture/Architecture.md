# VoiceIME 系统架构设计文档

> 版本：V1.0 | 日期：2026-05-21 | 状态：草稿
> 输入来源：VoiceIME PRD V1.0

---

# 1 技术难点识别

从 PRD 中标记的高风险技术点：

| # | 难点 | 风险维度 | 影响范围 | 当前应对 |
|---|------|---------|---------|---------|
| 1 | 全局键盘钩子可靠性 | 稳定性 | 进程崩溃后 Caps Lock 永久失效 | atexit + try/finally + Windows 自动卸载 DLL |
| 2 | ASR 推理延迟 | 性能 | 5s 音频 ≤ 2.5s 目标；CPU 密集型阻塞 | 独立线程 + int8 量化 + VirtualLock |
| 3 | 音频回调零阻塞 | 实时性 | 丢帧导致识别率下降 | ring buffer + 禁止回调内阻塞操作 |
| 4 | 剪贴板竞争窗口 | 可靠性 | 50ms 内其他进程操作剪贴板 | 恢复延迟可调 + 异常捕获 + 逐字符兜底 |
| 5 | 内存锁定影响 | 兼容性 | VirtualLock 3.5GB 影响系统其他程序 | 上限可调 + 开关可关闭 |
| 6 | 多线程事件循环 | 复杂度 | 5 个并发事件源，线程间通信设计 | queue.Queue + QTimer 轮询 |
| 7 | LLM 外部调用 | 可用性 | 超时/网络异常/DNS 失败 | 10s 超时 + DNS 5s + 保留原文降级 |
| 8 | pystray + PyQt6 共存 | 架构可行性 | 两个 UI 框架事件循环冲突 | pystray 独立线程 + PyQt6 主循环 |

---

# 2 架构模式决策

## 选择：模块化单体（Modular Monolith）

### 选择理由

- 单用户桌面应用，无需水平扩展；32GB 内存充裕无需进程隔离
- Python 单进程部署最简，避免多进程 IPC 复杂度
- 但模块边界必须清晰（recorder / asr / postprocess / output 自然解耦），允许未来按需拆分（如 ASR 进程隔离做内存管理）

### 放弃方案

| 方案 | 放弃理由 |
|------|---------|
| 纯单体 | 无模块边界约束，组件间随意引用导致耦合失控 |
| 微服务 | 单机桌面应用无水平扩展需求，IPC（socket/grpc）引入延迟和复杂度 |
| Serverless | 桌面应用无法使用；ASR 推理需要模型常驻内存，冷启动不可接受 |
| EDA | 事件驱动异步通信对实时音频处理引入不必要的消息延迟 |

---

# 3 模块分解

## 3.1 分层架构

```
┌──────────────────────────────────────────────────────────┐
│                    用户交互层 (UI)                        │
│   SystemTray    FloatingBar    SettingsWindow            │
│   HotwordWindow  HistoryWindow  FirstRunWizard           │
├──────────────────────────────────────────────────────────┤
│                    核心控制层 (Core)                      │
│   HotkeyManager  Recorder  ASREngine  PostProcessPipeline│
├──────────────────────────────────────────────────────────┤
│                    基础设施层 (Infra)                     │
│   ConfigManager  HistoryRepo  ModelManager  KeyringStore │
│   ContextEngine  ClipboardGuard                           │
├──────────────────────────────────────────────────────────┤
│                    输出层 (Output)                        │
│   ClipboardOutput  UIAOutput  KeyboardOutput             │
└──────────────────────────────────────────────────────────┘
```

## 3.2 模块清单与职责

| 模块 | 包路径 | 职责 | 依赖 | 优先级 |
|------|--------|------|------|--------|
| HotkeyManager | `voiceime.hotkey` | 全局键盘钩子注册/注销；keydown/keyup 事件分发；热键冲突检测 | 无 | P0 |
| Recorder | `voiceime.recorder` | 麦克风设备管理；16kHz Mono PCM 采集；ring buffer 写入；设备热插拔检测 | 无 | P0 |
| ASREngine | `voiceime.asr` | faster-whisper 模型加载/推理；VAD 参数透传；推理超时管理；VirtualLock 内存锁定 | Recorder(音频数据) | P0 |
| PostProcessPipeline | `voiceime.postprocess` | 编排后处理管道：标点规范化→繁简转换→热词替换→LLM 润色；管道可配置开关 | HotwordRepo, LLMClient | P1 |
| ClipboardGuard | `voiceime.output.clipboard` | 剪贴板备份/写入/恢复；50ms 延迟可调；异常降级到逐字符 | 无 | P0 |
| UIAOutput | `voiceime.output.uia` | UIAutomation Value Pattern 注入 | 无 | P0 |
| KeyboardOutput | `voiceime.output.keyboard` | pyautogui 逐字符输入兜底 | 无 | P0 |
| SystemTray | `voiceime.ui.tray` | pystray 托盘图标；4 状态切换；右键菜单；独立线程 | ConfigManager | P0 |
| FloatingBar | `voiceime.ui.floating` | PyQt6 悬浮录音条/结果条；波形动画；TopMost 不抢焦点 | 无 | P1 |
| SettingsWindow | `voiceime.ui.settings` | PyQt6 设置主窗口；5 Tab 配置 | ConfigManager, KeyringStore | P0 |
| ConfigManager | `voiceime.config` | config.json 读写；损坏检测 + .bak 恢复；默认值管理 | 无 | P0 |
| HistoryRepo | `voiceime.history` | SQLite CRUD；搜索 + 应用过滤；分页加载 | 无 | P1 |
| HotwordRepo | `voiceime.hotword` | hotwords.json 读写；增删改查；CSV 导入导出；小写匹配 | 无 | P1 |
| LLMClient | `voiceime.llm` | Claude/OpenAI/Ollama API 封装；超时 10s + DNS 5s；流式/非流式 | KeyringStore | P1 |
| KeyringStore | `voiceime.keyring` | Windows Credential Manager 读写；API Key 加密存取 | 无 | P1 |
| ModelManager | `voiceime.model` | 模型下载/完整性校验/版本管理；HuggingFace 断点续传 | ConfigManager | P0 |
| ContextEngine | `voiceime.context` | 读取聚焦窗口进程名/标题；匹配规则表；动态切换后处理行为 | ConfigManager | P2 |
| FirstRunWizard | `voiceime.ui.wizard` | 首次启动引导：麦克风检测→模型下载→热键确认 | Recorder, ModelManager | P0 |

## 3.3 模块依赖关系（DAG）

```
HotkeyManager ──────────────────────┐
       │ (keydown/keyup)            │
       ▼                            │
   Recorder ──(audio)──▶ ASREngine  │
                              │     │
                              ▼     │
                     PostProcessPipeline ◀── ContextEngine
                      │  │  │  │
                      │  │  │  └─(text)──▶ LLMClient ──▶ KeyringStore
                      │  │  └─(text)──▶ HotwordRepo
                      │  └─(text)──▶ OpenCC
                      └─(text)──▶ PunctNormalizer
                              │
                              ▼
                     OutputController
                      │    │    │
                      ▼    ▼    ▼
                 ClipboardGuard  UIAOutput  KeyboardOutput
                              │
                              ▼
                        HistoryRepo

SystemTray ◀── ConfigManager
SettingsWindow ◀── ConfigManager, KeyringStore
FloatingBar ◀── (直接由 CoreController 编排显隐)
FirstRunWizard ◀── Recorder, ModelManager
```

## 3.4 核心控制器（CoreController）

`voiceime.core.CoreController` 是唯一的全局编排者，负责：

1. 启动时初始化所有模块并注入依赖
2. 将 HotkeyManager 事件连接到 Recorder
3. 将 Recorder 输出连接到 ASREngine
4. 将 ASREngine 输出连接到 PostProcessPipeline
5. 将 PostProcessPipeline 输出连接到 OutputController
6. 管理全局状态机（就绪→录音→识别→确认→上屏）
7. 监听系统托盘指令（暂停/恢复/退出）

**设计约束**：CoreController 不包含任何业务逻辑，仅做事件路由和状态流转。每个模块通过明确的接口（Protocol/ABC）通信。

---

# 4 线程模型

## 4.1 线程架构

```
┌───────────────────────────────────────────────────────────┐
│  主线程（PyQt6 QApplication 事件循环）                     │
│   · CoreController 状态机                                 │
│   · FloatingBar / SettingsWindow / HistoryWindow           │
│   · PostProcessPipeline 编排                              │
│   · OutputController 上屏执行                              │
│   · QTimer 50ms 轮询消费各队列                             │
├───────────────────────────────────────────────────────────┤
│  托盘线程（pystray 独立线程）                              │
│   · SystemTray 图标 + 右键菜单                             │
│   · 通过 cmd_queue 向主线程发送指令                         │
├───────────────────────────────────────────────────────────┤
│  热键监听线程（pynput Listener）                           │
│   · WH_KEYBOARD_LL 全局钩子                               │
│   · keydown/keyup 事件通过 hotkey_queue 通知主线程          │
├───────────────────────────────────────────────────────────┤
│  音频线程（sounddevice InputStream 回调）                   │
│   · PCM 采集回调，写入 ring buffer                         │
│   · 禁止在回调中做任何阻塞操作                              │
├───────────────────────────────────────────────────────────┤
│  推理线程（ThreadPoolExecutor 单线程）                      │
│   · faster-whisper CPU 推理（阻塞型）                      │
│   · 推理结果通过 result_queue 回传主线程                    │
├───────────────────────────────────────────────────────────┤
│  LLM 线程（ThreadPoolExecutor 单线程）                      │
│   · LLM API HTTP 调用（阻塞型 I/O）                       │
│   · 结果通过 llm_queue 回传主线程                           │
└───────────────────────────────────────────────────────────┘

线程间通信：queue.Queue（线程安全 FIFO）
主线程消费时机：QTimer 定时轮询（50ms 间隔）
```

## 4.2 队列定义

| 队列名 | 生产者 | 消费者 | 消息类型 |
|--------|--------|--------|---------|
| `hotkey_queue` | HotkeyManager 线程 | 主线程 CoreController | `HotKeyEvent(key, action)` |
| `cmd_queue` | SystemTray 线程 | 主线程 CoreController | `TrayCommand(action)` |
| `audio_queue` | sounddevice 回调 | Recorder 模块 | `numpy.ndarray` PCM chunk |
| `result_queue` | ASREngine 线程 | 主线程 CoreController | `ASRResult(text, language, duration)` |
| `llm_queue` | LLMClient 线程 | 主线程 CoreController | `LLMResult(text, error)` |

## 4.3 线程安全约束

1. **PyQt6 UI 操作只能在主线程执行**：所有来自其他线程的 UI 更新必须通过信号槽（`pyqtSignal`）或 QTimer 轮询队列
2. **sounddevice 回调零阻塞**：回调内只做 `ring_buffer.write(data)`，不做任何 Python 对象分配或阻塞调用
3. **faster-whisper 推理串行**：`ThreadPoolExecutor(max_workers=1)` 确保同一时间只有一次推理
4. **ConfigManager 读写加锁**：`threading.RLock` 保护 config.json 的读写操作

---

# 5 技术栈选型表

| 层级 | 选型 | 选择理由 | 放弃的替代方案 |
|------|------|---------|---------------|
| UI 框架 | PyQt6 | 现代外观，丰富控件，波形动画性能好，Qt.ToolTip 实现 TopMost 不抢焦点 | tkinter（控件少，外观旧）；PySide6（LGPL 无需商业授权，但社区资源少于 PyQt6） |
| 系统托盘 | pystray | 轻量，独立线程运行，不依赖 PyQt6 事件循环 | PyQt6 QSystemTrayIcon（与主循环耦合，崩溃时托盘跟着死） |
| 全局热键 | pynput | 跨应用全局钩子，keydown/keyup 区分，Python 原生 | ctypes 直接调 WH_KEYBOARD_LL（可更细粒度控制但开发成本高，pynput 已封装） |
| 音频录制 | sounddevice + numpy | 低延迟 PCM 流，直接输出 numpy array 供模型消费，跨平台 | pyaudio（依赖 PortAudio 编译，Windows 安装易出问题） |
| VAD | faster-whisper 内置 Silero | 零额外依赖，参数直接透传 | webrtcvad（不支持中文低能量尾音，需手动调参） |
| ASR 推理 | faster-whisper (CTranslate2) | pip 直接安装，CPU AVX2 性能优秀，int8 量化开箱即用 | whisper.cpp（Vulkan 待验证，编译链复杂）；SenseVoice（中英混说待测，非首选） |
| 文本上屏 | pyperclip + pyautogui | 分层 Fallback 覆盖 99% 场景；pywinauto UIA 补充 | win32clipboard 直接操作（API 复杂，pyperclip 已封装） |
| LLM 调用 | anthropic / openai SDK | 按用户配置切换，官方 SDK 稳定 | httpx 手动调用（需自行处理重试、流式、错误码） |
| 繁简转换 | opencc-python-reimplemented | 纯 Python 封装，无 C++ 编译依赖 | opencc（需编译 C++ 库，Windows 安装困难） |
| 配置存储 | JSON | 人类可读，便于手动编辑和版本控制 | TOML（Python 3.11+ 内置，但 JSON 生态更广）；YAML（需额外依赖） |
| 历史记录 | SQLite (sqlite3) | 零依赖，本地轻量数据库，支持全文搜索 | JSON 文件（搜索性能差，数据量大时加载慢） |
| API Key 存储 | keyring → Windows Credential Manager | 系统级加密，不明文存储 | 自定义加密（重复造轮子，安全性不可审计） |
| 打包分发 | PyInstaller | 单文件可执行，Windows 原生 | Nuitka（编译为 C，性能更好但构建复杂度高，MVP 不需要） |
| 日志 | logging (stdlib) | Python 内置，无需额外依赖 | loguru（更美观但引入额外依赖，MVP 不需要） |
| 缓存 | 无 | 单用户桌面应用无需缓存层 | Redis（杀鸡用牛刀） |
| 消息队列 | queue.Queue (stdlib) | 线程安全 FIFO，5 个并发源足够 | ZeroMQ（过度设计） |

---

# 6 核心数据模型（ER 描述）

## 6.1 history.sqlite

```
Table: history
  - id:                  INTEGER  PRIMARY KEY AUTOINCREMENT
  - created_at:          TEXT     NOT NULL                // ISO 8601: "2026-05-21T14:32:00"
  - text:                TEXT     NOT NULL                // 最终输出文本（润色后）
  - raw_text:            TEXT                             // ASR 原始输出（润色前），可为空
  - language:            TEXT                             // "zh" / "en" / "mixed"
  - app_name:            TEXT                             // 焦点窗口进程名，如 "Code.exe"
  - app_title:           TEXT                             // 焦点窗口标题
  - audio_duration_ms:   INTEGER                          // 录音时长
  - inference_time_ms:   INTEGER                          // 推理耗时
  - is_polished:         BOOLEAN  DEFAULT 0               // 是否经过 LLM 润色

Index: idx_history_created  ON (created_at DESC)          // 按时间倒序浏览
Index: idx_history_app      ON (app_name)                 // 按应用过滤
Index: idx_history_text     ON (text)                     // 全文搜索（LIKE 前缀匹配）
```

## 6.2 config.json

```
路径: %APPDATA%\VoiceIME\config.json

结构:
  hotkey:                     string   // 热键名称，如 "caps_lock"
  asr.model:                  string   // 模型名，如 "large-v3-turbo"
  asr.quantization:           string   // 量化精度，如 "int8"
  asr.device:                 string   // 推理后端，"cpu" | "vulkan"
  asr.language:               string   // 语言设定，"auto" | "zh" | "en"
  asr.beam_size:              int      // 解码 beam 数
  asr.vad_filter:             bool     // VAD 开关
  asr.vad_threshold:          float    // VAD 阈值 0.0-1.0
  postprocess.punct_normalize: bool    // 标点规范化开关
  postprocess.t2s_enabled:    bool     // 繁简转换开关
  postprocess.hotword_enabled: bool    // 热词替换开关
  llm.provider:               string   // "" | "claude" | "openai" | "ollama"
  llm.api_key_stored_in_keyring: bool  // API Key 存储位置标记
  llm.model_id:               string   // 模型 ID
  llm.polish_mode:            string   // "manual" | "auto"
  llm.system_prompt:          string   // 默认 System Prompt
  llm.timeout_seconds:        int      // 超时秒数
  ui.quick_mode:              bool     // 快速模式开关
  ui.memory_lock:             bool     // 内存锁定开关
  ui.memory_lock_limit_gb:    float    // 内存锁定上限 GB
  ui.auto_restore_clipboard:  bool     // 自动恢复剪贴板开关
  ui.clipboard_restore_delay_ms: int   // 剪贴板恢复延迟 ms
  ui.min_record_ms:           int      // 最短录音时长 ms
  ui.max_record_s:            int      // 最长录音时长 s
  advanced.log_level:         string   // "DEBUG" | "INFO" | "WARNING" | "ERROR"
  advanced.log_path:          string   // 日志路径
```

## 6.3 hotwords.json

```
路径: %APPDATA%\VoiceIME\hotwords.json

结构: Array<{ trigger: string, replace: string, case_sensitive: bool }>
  trigger:     触发词（存储时统一小写，当 case_sensitive=false）
  replace:     替换词
  case_sensitive: 是否大小写敏感（默认 false）
```

## 6.4 context_rules.json（P2）

```
路径: %APPDATA%\VoiceIME\context_rules.json

结构: Array<{ app_name: string, title_pattern: string, actions: ContextActions }>
  app_name:       进程名匹配，如 "Code.exe"
  title_pattern:  窗口标题正则，如 ".*\.py.*"，空串表示任意
  actions:
    quick_mode:      bool     // 强制快速上屏
    polish_mode:     string   // "off" | "manual" | "auto"
    system_prompt:   string   // 覆盖默认 System Prompt
```

## 6.5 关系

```
config.json.asr.model ──→ ModelManager (决定加载哪个模型)
config.json.llm.provider ──→ LLMClient (决定调用哪个 API)
hotwords.json.trigger ──→ PostProcessPipeline.hotword (后处理热词替换)
context_rules.json.app_name ──→ ContextEngine (上下文规则匹配)
history.app_name ──→ context_rules.json.app_name (间接关联，规则匹配影响后处理行为)
```

---

# 7 关键 API 规范（Top 5）

> VoiceIME 为本地单进程应用，以下"API"指模块间接口调用规范，非 HTTP API。

| Method | 接口 | 输入 | 输出 | 说明 |
|--------|------|------|------|------|
| `start()` | Recorder.start() | `{ sample_rate: 16000, channels: 1 }` | `None` | 开始录音，启动 sounddevice InputStream |
| `stop()` | Recorder.stop() | `None` | `{ audio: ndarray, duration_ms: int }` | 停止录音，返回完整 PCM 数据 |
| `transcribe()` | ASREngine.transcribe() | `{ audio: ndarray, language: str, vad_filter: bool }` | `{ text: str, language: str, inference_ms: int }` | 执行 ASR 推理，30s 超时 |
| `process()` | PostProcessPipeline.process() | `{ text: str, raw_text: str, context: ContextInfo }` | `{ text: str, is_polished: bool }` | 执行后处理管道，LLM 润色可选 |
| `output()` | OutputController.output() | `{ text: str, target: WindowInfo }` | `{ success: bool, method: str }` | 文本上屏，三层 Fallback |

---

# 8 韧性方案

## 8.1 韧性方案摘要

| 维度 | 方案 | 降级策略 |
|------|------|---------|
| 认证 | 不适用（单用户本地应用） | — |
| 限流 | ASR 推理串行（单线程池）；LLM 超时 10s + DNS 5s | 推理排队等待；LLM 超时保留原文 |
| 剪贴板安全 | 备份→写入→Ctrl+V→延迟恢复 | 恢复失败→日志告警 + 文本保留在剪贴板；剪贴板锁定→逐字符输入 |
| 配置容灾 | config.json 损坏→重命名 .bak →新建默认 | hotwords.json 同理；SQLite PRAGMA integrity_check → .bak →新建 |
| 模型容灾 | 模型文件缺失/损坏→降级模式（仅托盘，ASR 禁用） | 模型加载失败→托盘红色→引导重新下载 |
| 进程安全 | atexit + try/finally 清理钩子；Win32 命名互斥体防多实例 | 进程崩溃→Windows 自动卸载 WH_KEYBOARD_LL DLL |
| 内存安全 | VirtualLock 锁定上限 3.5GB；提供开关 | 关闭开关→允许换出→二次唤醒延迟增加 |
| LLM 可用性 | 超时 10s；DNS 5s；支持取消；网络异常保留原文 | LLM 不可用→后处理管道跳过润色步骤 |
| 麦克风异常 | 录音期间设备断开→立即停止→悬浮条提示 | 无麦克风→首次启动引导页阻止继续 |
| Windows 休眠 | VirtualLock 休眠恢复后仍有效；音频设备下次热键触发时重新初始化 | 设备不可用→自动重开录音流 |

## 8.2 安全需求落实（来自 PRD §4.3）

| 安全需求 | 落实方案 | 模块 |
|---------|---------|------|
| 语音数据 100% 本地处理 | ASREngine 仅调用 faster-whisper 本地推理；录音数据不离开进程内存 | ASREngine |
| API Key 不写入明文配置 | KeyringStore 通过 keyring 库写入 Windows Credential Manager；config.json 仅存 `api_key_stored_in_keyring: true` | KeyringStore |
| 历史记录仅本地 | SQLite 文件位于 `%APPDATA%\VoiceIME\`；无任何云同步机制 | HistoryRepo |
| 进程崩溃钩子自动注销 | atexit 注册 cleanup + try/finally 双保险；Windows 进程终止自动卸载 DLL | HotkeyManager |
| LLM 润色仅用户主动触发 | 默认 polish_mode=manual；自动润色需用户显式开启；LLM 请求不含语音原始数据 | LLMClient, PostProcessPipeline |
| 剪贴板数据保护 | 备份内容仅存进程内存；上屏完成后立即恢复并清除备份引用 | ClipboardGuard |

---

# 9 项目目录结构

```
voiceime/
├── __init__.py
├── __main__.py                    # 入口：python -m voiceime
├── core.py                        # CoreController 全局编排
├── hotkey/
│   ├── __init__.py
│   ├── manager.py                 # HotkeyManager：全局钩子注册/注销
│   └── hook.py                    # pynput Listener 封装
├── recorder/
│   ├── __init__.py
│   ├── device.py                  # 麦克风设备管理
│   └── stream.py                  # sounddevice InputStream + ring buffer
├── asr/
│   ├── __init__.py
│   ├── engine.py                  # ASREngine：faster-whisper 封装
│   └── memory.py                  # VirtualLock 内存锁定
├── postprocess/
│   ├── __init__.py
│   ├── pipeline.py                # PostProcessPipeline 编排
│   ├── punct.py                   # 标点规范化
│   ├── converter.py               # 繁简转换 (OpenCC)
│   └── hotword.py                 # 热词替换
├── output/
│   ├── __init__.py
│   ├── controller.py              # OutputController：三层 Fallback 编排
│   ├── clipboard.py               # ClipboardGuard：剪贴板备份/恢复
│   ├── uia.py                     # UIAutomation Value Pattern
│   └── keyboard.py                # pyautogui 逐字符输入
├── llm/
│   ├── __init__.py
│   ├── client.py                  # LLMClient：Claude/OpenAI/Ollama 封装
│   └── prompts.py                 # System Prompt 模板管理
├── config/
│   ├── __init__.py
│   ├── manager.py                 # ConfigManager：config.json 读写
│   └── defaults.py                # 默认配置值定义
├── history/
│   ├── __init__.py
│   └── repository.py              # HistoryRepo：SQLite CRUD
├── hotword/
│   ├── __init__.py
│   └── repository.py              # HotwordRepo：hotwords.json 读写
├── context/
│   ├── __init__.py
│   ├── engine.py                  # ContextEngine：窗口检测 + 规则匹配
│   └── window.py                  # 焦点窗口信息获取
├── model/
│   ├── __init__.py
│   ├── manager.py                 # ModelManager：下载/校验/版本管理
│   └── downloader.py              # HuggingFace 断点续传下载
├── keyring/
│   ├── __init__.py
│   └── store.py                   # KeyringStore：API Key 加密存取
├── ui/
│   ├── __init__.py
│   ├── tray.py                    # SystemTray：pystray 托盘
│   ├── floating.py                # FloatingBar：悬浮录音条/结果条
│   ├── settings.py                # SettingsWindow：5 Tab 设置
│   ├── hotword_window.py          # HotwordWindow：热词词库管理
│   ├── history_window.py          # HistoryWindow：历史记录
│   ├── wizard.py                  # FirstRunWizard：首次引导
│   └── resources/
│       ├── icons/                 # 托盘图标（绿/黄/红/灰）
│       └── styles/                # QSS 样式表
└── utils/
    ├── __init__.py
    ├── single_instance.py         # Win32 命名互斥体
    ├── log.py                     # 日志配置
    └── paths.py                   # %APPDATA% 路径管理
```

---

# 10 全局状态机

```
                    ┌──────────────┐
                    │  UNINITIALIZED │ ← 程序启动
                    └──────┬───────┘
                           │ 模型加载完成 + 麦克风就绪
                           ▼
                    ┌──────────────┐
            ┌──────│    READY      │──────┐
            │      └──────────────┘      │
            │ 用户暂停                    │ 热键按下
            ▼                            ▼
    ┌──────────────┐            ┌──────────────┐
    │   PAUSED      │            │  RECORDING   │
    └──────────────┘            └──────┬───────┘
       │ 用户恢复                       │ 热键松开
       └────────────────────────────────┤
                                        ▼
                                 ┌──────────────┐
                                 │  INFERRING   │
                                 └──────┬───────┘
                                        │ 推理完成
                                        ▼
                                 ┌──────────────┐
                                 │  CONFIRMING  │ ← 快速模式跳过
                                 └──────┬───────┘
                                        │ 用户确认
                                        ▼
                                 ┌──────────────┐
                                 │  OUTPUTTING  │
                                 └──────┬───────┘
                                        │ 上屏完成
                                        ▼
                                    回到 READY
```

异常状态：

| 异常状态 | 触发条件 | 恢复路径 |
|---------|---------|---------|
| ERROR_MIC | 麦克风断开/无权限 | 设备重连后自动恢复到 READY |
| ERROR_MODEL | 模型加载失败 | 托盘红色，引导重新下载 |
| ERROR_INFERENCE_TIMEOUT | 推理超时 30s | 显示提示，用户选择重录/取消 |
| ERROR_LLM_TIMEOUT | LLM 润色超时 10s | 保留原文，用户可上屏原文 |
| ERROR_CLIPBOARD | 剪贴板操作失败 | 降级到逐字符输入 |

---

# 11 关键时序

## 11.1 热键录音→识别→上屏（Happy Path）

```
User          HotkeyManager    Recorder    ASREngine    PostProcess    OutputController    HistoryRepo
 │                 │               │           │             │               │                 │
 │──keydown──────▶│               │           │             │               │                 │
 │                │──start()─────▶│           │             │               │                 │
 │                │               │──PCM──▶   │             │               │                 │
 │──keyup────────▶│               │           │             │               │                 │
 │                │──stop()──────▶│           │             │               │                 │
 │                │               │──audio──▶ │             │               │                 │
 │                │               │           │──transcribe▶│               │                 │
 │                │               │           │──result───▶ │               │                 │
 │                │               │           │             │──process()──▶ │                 │
 │                │               │           │             │──text───────▶ │                 │
 │                │               │           │             │               │──output()──▶    │
 │◀───────────────────────────────────────────────────────────text injected──│                 │
 │                │               │           │             │               │──save()───────▶ │
```

## 11.2 剪贴板保护流程

```
OutputController                ClipboardGuard                    System
     │                              │                               │
     │──backup_clipboard()────────▶ │                               │
     │                              │──OpenClipboard()─────────────▶│
     │                              │──GetClipboardData()──────────▶│
     │                              │──CloseClipboard()────────────▶│
     │                              │                               │
     │──write_and_paste(text)────▶ │                               │
     │                              │──SetClipboardData(text)──────▶│
     │                              │──SendInput(Ctrl+V)───────────▶│
     │                              │──Sleep(50ms)                  │
     │                              │                               │
     │──restore_clipboard()───────▶ │                               │
     │                              │──SetClipboardData(backup)────▶│
     │                              │──CloseClipboard()────────────▶│
```

---

# 12 关键设计决策

## 12.1 为什么剪贴板方案优先于 UIAutomation？

PRD §3.4.2 已明确：UIAutomation Value Pattern 在 Chrome/Electron/微信等主流应用中大多不支持。剪贴板 + Ctrl+V 覆盖 99% 场景，UIA 仅作为 Win32/WPF 标准文本框的补充。

## 12.2 为什么用 QTimer 轮询而非 PyQt6 信号槽跨线程通信？

`pyqtSignal` 跨线程时通过 Qt 事件循环投递，与 pynput/sounddevice 的回调线程配合存在时序不确定性。QTimer 轮询 `queue.Queue` 是最简单可靠的方式：队列保证 FIFO 顺序，50ms 轮询间隔对用户操作（热键触发→录音条出现 < 50ms 要求）足够响应。

## 12.3 为什么 PyInstaller 而非 Nuitka？

MVP 阶段打包速度和简单性优先。PyInstaller 单文件模式足够满足分发需求。Nuitka 编译为 C 虽然启动更快，但构建链复杂（需 C 编译器），且 ASR 推理性能瓶颈在 CPU 计算而非 Python 解释器开销。

---

# 13 架构风险点

> **CPU 推理性能是最脆弱维度**。5s 音频 ≤ 2.5s 目标依赖 int8 量化 + AVX2 指令集，若实测不达标需切 Vulkan 后端（引入 whisper.cpp 编译链复杂度）或降级模型（牺牲准确率）。多线程模型下音频回调与推理线程的资源竞争需实测验证。

---

# 架构决策摘要（供下游 Skill 04 优先读取，≤300字）

> 技术栈：Python 3.11+ / PyQt6 / pynput / sounddevice / faster-whisper(CTranslate2) / pystray / SQLite / keyring / PyInstaller。
> 架构模式：模块化单体，单进程 5 线程（主线程 PyQt6 + 托盘 + 热键 + 音频 + 推理），queue.Queue + QTimer 50ms 轮询通信。
> 核心数据模型：config.json（全局配置）、history.sqlite（识别历史）、hotwords.json（热词映射）、context_rules.json（P2 上下文规则）。
> 最大风险点：CPU 推理性能（5s ≤ 2.5s 目标待实测），不达标需切 Vulkan 后端或降级模型。
