# VoiceIME 开发编排文档

> 版本：V1.0 | 日期：2026-05-21 | 状态：草稿
> 输入来源：VoiceIME PRD V1.0 + Architecture V1.0
> 开发模式：2 Agent 并行 + 灵活周期

---

# 1 模块依赖图（DAG）

## 1.1 分层依赖关系

```
Level 0 · 基础设施（无外部依赖）
├── voiceime/utils/paths.py          APPDATA 路径管理
├── voiceime/utils/log.py            日志配置
├── voiceime/utils/single_instance.py 命名互斥体
├── voiceime/config/defaults.py      默认配置值
└── voiceime/config/manager.py       config.json 读写

Level 1 · 数据持久化（依赖 Level 0）
├── voiceime/keyring/store.py        ← config (路径)
├── voiceime/hotword/repository.py   ← config (路径)
└── voiceime/history/repository.py   ← config (路径)

Level 2 · 独立硬件接口（依赖 Level 0）
├── voiceime/hotkey/manager.py       ← config (热键配置)
├── voiceime/hotkey/hook.py          ← manager (回调)
├── voiceime/recorder/device.py      (设备枚举)
├── voiceime/recorder/stream.py      ← device (录音流)
├── voiceime/output/clipboard.py     ← config (延迟参数)
├── voiceime/output/uia.py           (独立)
└── voiceime/output/keyboard.py      (独立)

Level 3 · 推理与后处理（依赖 Level 0-2）
├── voiceime/model/manager.py        ← config (模型名)
├── voiceime/model/downloader.py     ← manager (下载任务)
├── voiceime/asr/engine.py           ← model + recorder (音频数据)
├── voiceime/asr/memory.py           ← config (锁定参数)
├── voiceime/postprocess/punct.py    (独立纯函数)
├── voiceime/postprocess/converter.py (独立)
├── voiceime/postprocess/hotword.py  ← hotword/repo (词库数据)
├── voiceime/llm/client.py           ← keyring (API Key)
├── voiceime/llm/prompts.py          ← config (默认 prompt)
└── voiceime/context/engine.py       ← config (规则) [P2]

Level 4 · 编排层（依赖 Level 0-3）
├── voiceime/postprocess/pipeline.py ← punct + converter + hotword + llm
├── voiceime/output/controller.py    ← clipboard + uia + keyboard
└── voiceime/core.py                 ← ALL modules

Level 5 · UI 层（依赖 Level 0-4）
├── voiceime/ui/tray.py              ← config + core (状态)
├── voiceime/ui/floating.py          ← core (状态机)
├── voiceime/ui/settings.py          ← config + keyring
├── voiceime/ui/history_window.py    ← history
├── voiceime/ui/hotword_window.py    ← hotword
├── voiceime/ui/wizard.py            ← recorder + model
└── voiceime/__main__.py             ← core (入口)
```

## 1.2 关键路径（Critical Path）

```
config → model → asr → core → output
```

推理管线是产品核心价值，任何阻塞在 model/asr 上的延迟都直接影响用户体验。
次要关键路径：`hotkey → recorder → asr`（音频采集质量影响识别率）。

## 1.3 可并行开发的模块组

| 并行组 | Agent A（infra-agent） | Agent B（pipeline-agent） |
|--------|----------------------|--------------------------|
| Group 1 | utils + config + defaults | hotkey + recorder |
| Group 2 | keyring + hotword + history | asr + model + memory |
| Group 3 | model/downloader | output (clipboard + uia + keyboard) |
| Group 4 | UI (tray + floating + settings + wizard) | postprocess + llm + core |
| Group 5 | UI (history_window + hotword_window) | context + 性能调优 |

---

# 2 接口契约定义

> VoiceIME 为本地单进程应用，接口契约以 Python Protocol 形式定义。
> **契约一旦定义，不得单方面修改，变更需双方 Agent 确认。**

## CONTRACT-01: HotkeyProvider

```
CONTRACT: HotkeyProvider
  Provider:  voiceime/hotkey/manager.py  (HotkeyManager)
  Consumer:  voiceime/core.py            (CoreController)
  Protocol:
    class HotkeyProvider(Protocol):
        def start(self) -> None:
            """启动全局键盘钩子监听。"""

        def stop(self) -> None:
            """注销键盘钩子，释放系统资源。"""

        def set_callback(self, on_keydown: Callable[[], None],
                               on_keyup: Callable[[], None]) -> None:
            """注册 keydown/keyup 回调。"""

        @property
        def current_hotkey(self) -> str:
            """返回当前热键名称，如 'caps_lock'。"""

  Queue:
    hotkey_queue: Queue[HotKeyEvent]
    HotKeyEvent = namedtuple('HotKeyEvent', ['key', 'action'])
    action: 'down' | 'up'

  Error:
    HotkeyConflictError: 热键已被其他程序占用
    HookRegistrationError: WH_KEYBOARD_LL 注册失败

  变更策略: 双方 Agent 确认后方可修改
```

## CONTRACT-02: AudioProvider

```
CONTRACT: AudioProvider
  Provider:  voiceime/recorder/stream.py   (RecorderStream)
  Consumer:  voiceime/core.py             (CoreController)
             voiceime/asr/engine.py       (ASREngine)
  Protocol:
    class AudioProvider(Protocol):
        def start_recording(self) -> None:
            """启动 sounddevice InputStream，16kHz Mono PCM。"""

        def stop_recording(self) -> AudioData:
            """停止录音，返回完整 PCM 数据。"""

        @property
        def is_recording(self) -> bool:
            """当前是否正在录音。"""

        @property
        def duration_ms(self) -> int:
            """当前录音已持续毫秒数。"""

        @property
        def devices(self) -> list[DeviceInfo]:
            """返回可用麦克风设备列表。"""

  Data:
    AudioData = namedtuple('AudioData', ['pcm', 'duration_ms', 'sample_rate'])
      pcm:          numpy.ndarray  # shape: (N,), dtype: float32
      duration_ms:  int
      sample_rate:  int            # 固定 16000

    DeviceInfo = namedtuple('DeviceInfo', ['id', 'name', 'is_default'])

  Error:
    DeviceNotFoundError: 无可用麦克风
    DeviceDisconnectedError: 录音期间设备断开

  变更策略: 双方 Agent 确认后方可修改
```

## CONTRACT-03: ASRProvider

```
CONTRACT: ASRProvider
  Provider:  voiceime/asr/engine.py        (ASREngine)
  Consumer:  voiceime/core.py             (CoreController)
  Protocol:
    class ASRProvider(Protocol):
        def load_model(self) -> None:
            """加载 faster-whisper 模型到内存。耗时操作，在独立线程调用。"""

        def transcribe(self, audio: numpy.ndarray) -> ASRResult:
            """执行语音识别推理。30s 超时。"""

        @property
        def is_loaded(self) -> bool:
            """模型是否已加载就绪。"""

        def unload_model(self) -> None:
            """卸载模型，释放内存。"""

  Data:
    ASRResult = namedtuple('ASRResult', [
        'text',           # str: 识别文本
        'language',       # str: 'zh' | 'en' | 'mixed'
        'inference_ms',   # int: 推理耗时毫秒
        'segments'        # list[dict]: 分段详情
    ])

  Queue:
    result_queue: Queue[ASRResult]

  Error:
    ModelNotLoadedError: 模型未加载
    InferenceTimeoutError: 推理超时 30s
    InferenceError: 推理过程异常

  变更策略: 双方 Agent 确认后方可修改
```

## CONTRACT-04: PostProcessProvider

```
CONTRACT: PostProcessProvider
  Provider:  voiceime/postprocess/pipeline.py  (PostProcessPipeline)
  Consumer:  voiceime/core.py                 (CoreController)
  Protocol:
    class PostProcessProvider(Protocol):
        def process(self, text: str, context: ProcessContext | None = None
                    ) -> ProcessResult:
            """执行完整后处理管道（标点→繁简→热词→LLM 润色）。"""

        def polish_only(self, text: str, context: ProcessContext | None = None
                        ) -> ProcessResult:
            """仅执行 LLM 润色，跳过其他步骤。"""

        @property
        def config(self) -> PipelineConfig:
            """当前管道配置。"""

  Data:
    ProcessContext = namedtuple('ProcessContext', [
        'app_name',       # str | None
        'app_title',      # str | None
    ])

    ProcessResult = namedtuple('ProcessResult', [
        'text',           # str: 处理后文本
        'is_polished',    # bool: 是否经过 LLM 润色
        'steps_applied',  # list[str]: 已执行的步骤名
    ])

  Error:
    LLMTimeoutError: LLM 超时 10s（应返回原文 + is_polished=False）
    LLMError: LLM 调用失败（应返回原文 + is_polished=False）

  变更策略: 双方 Agent 确认后方可修改
```

## CONTRACT-05: OutputProvider

```
CONTRACT: OutputProvider
  Provider:  voiceime/output/controller.py   (OutputController)
  Consumer:  voiceime/core.py               (CoreController)
  Protocol:
    class OutputProvider(Protocol):
        def output(self, text: str) -> OutputResult:
            """文本上屏，执行三层 Fallback。"""

  Data:
    OutputResult = namedtuple('OutputResult', [
        'success',    # bool
        'method',     # str: 'clipboard' | 'uia' | 'keyboard'
        'error',      # str | None: 失败原因
    ])

  Fallback 顺序:
    1. clipboard: 备份→写入→Ctrl+V→延迟恢复
    2. uia: UIAutomation Value Pattern
    3. keyboard: pyautogui 逐字符输入

  变更策略: 双方 Agent 确认后方可修改
```

## CONTRACT-06: ConfigProvider

```
CONTRACT: ConfigProvider
  Provider:  voiceime/config/manager.py      (ConfigManager)
  Consumer:  ALL modules
  Protocol:
    class ConfigProvider(Protocol):
        def get(self, key: str, default: Any = None) -> Any:
            """获取配置值，支持点分路径如 'asr.model'。"""

        def set(self, key: str, value: Any) -> None:
            """设置配置值并立即持久化。"""

        def reload(self) -> None:
            """从磁盘重新加载配置（损坏时自动恢复）。"""

        @property
        def data_dir(self) -> Path:
            """返回 %APPDATA%\VoiceIME\ 路径。"""

  Error:
    ConfigCorruptedError: 配置文件损坏（自动恢复为默认值）

  变更策略: 双方 Agent 确认后方可修改
```

## CONTRACT-07: HistoryProvider

```
CONTRACT: HistoryProvider
  Provider:  voiceime/history/repository.py  (HistoryRepo)
  Consumer:  voiceime/core.py               (CoreController)
             voiceime/ui/history_window.py   (HistoryWindow)
  Protocol:
    class HistoryProvider(Protocol):
        def save(self, record: HistoryRecord) -> int:
            """保存一条识别记录，返回 id。"""

        def search(self, query: str, app_filter: str | None = None,
                   limit: int = 50, offset: int = 0) -> list[HistoryRecord]:
            """搜索历史记录。"""

        def get_by_id(self, record_id: int) -> HistoryRecord | None:
            """按 ID 查询。"""

        def delete(self, record_id: int) -> bool:
            """删除单条记录。"""

        def clear_all(self) -> int:
            """清空全部记录，返回删除条数。"""

        @property
        def total_count(self) -> int:
            """总记录数。"""

  Data:
    HistoryRecord = dataclass:
        id:                int | None
        created_at:        str          # ISO 8601
        text:              str
        raw_text:          str | None
        language:          str | None
        app_name:          str | None
        app_title:         str | None
        audio_duration_ms: int | None
        inference_time_ms: int | None
        is_polished:       bool

  Error:
    DatabaseCorruptedError: SQLite 损坏（自动备份 + 重建）

  变更策略: 双方 Agent 确认后方可修改
```

## CONTRACT-08: ModelProvider

```
CONTRACT: ModelProvider
  Provider:  voiceime/model/manager.py       (ModelManager)
  Consumer:  voiceime/asr/engine.py         (ASREngine)
             voiceime/ui/wizard.py          (FirstRunWizard)
  Protocol:
    class ModelProvider(Protocol):
        def ensure_model(self, model_name: str, quantization: str
                         ) -> Path:
            """确保模型文件存在，缺失则触发下载。返回模型目录路径。"""

        def verify_model(self, model_dir: Path) -> bool:
            """校验模型文件完整性（model.bin + config.json + vocabulary.txt）。"""

        @property
        def download_progress(self) -> DownloadProgress | None:
            """当前下载进度，无下载任务时返回 None。"""

        @property
        def available_models(self) -> list[str]:
            """本地已有的模型列表。"""

  Data:
    DownloadProgress = namedtuple('DownloadProgress', [
        'downloaded_bytes',   # int
        'total_bytes',        # int
        'speed_bps',          # float
        'eta_seconds',        # float
    ])

  Error:
    DownloadError: 下载失败（重试 3 次后抛出）
    ModelCorruptedError: 模型文件不完整

  变更策略: 双方 Agent 确认后方可修改
```

## CONTRACT-09: LLMProvider

```
CONTRACT: LLMProvider
  Provider:  voiceime/llm/client.py         (LLMClient)
  Consumer:  voiceime/postprocess/pipeline.py
  Protocol:
    class LLMProvider(Protocol):
        def polish(self, text: str, system_prompt: str | None = None
                   ) -> LLMResult:
            """调用 LLM API 润色文本。10s 超时。"""

        def cancel(self) -> None:
            """取消当前进行中的 LLM 请求。"""

        def test_connection(self) -> bool:
            """测试 API 连接是否可用。"""

        @property
        def is_configured(self) -> bool:
            """是否已配置 API Key。"""

  Data:
    LLMResult = namedtuple('LLMResult', [
        'text',         # str: 润色后文本
        'is_success',   # bool
        'error',        # str | None
    ])

  Queue:
    llm_queue: Queue[LLMResult]

  Error:
    LLMTimeoutError: 10s 超时
    LLMAuthError: API Key 无效
    LLMConnectionError: 网络异常 / DNS 5s 超时

  变更策略: 双方 Agent 确认后方可修改
```

## CONTRACT-10: StateMachine

```
CONTRACT: StateMachine
  Provider:  voiceime/core.py               (CoreController)
  Consumer:  voiceime/ui/floating.py        (FloatingBar)
             voiceime/ui/tray.py            (SystemTray)
  States:
    UNINITIALIZED → READY ⇄ RECORDING → INFERRING → CONFIRMING → OUTPUTTING → READY
    PAUSED (从 READY 进入)
    ERROR_MIC / ERROR_MODEL / ERROR_INFERENCE_TIMEOUT / ERROR_LLM_TIMEOUT / ERROR_CLIPBOARD

  Events (via pyqtSignal):
    state_changed(new_state: str)
    recording_progress(duration_ms: int, waveform: list[float])
    asr_result_received(result: ASRResult)
    llm_result_received(result: LLMResult)
    error_occurred(error_state: str, message: str)

  变更策略: 双方 Agent 确认后方可修改
```

---

# 3 项目路线图

## Phase 1 · MVP（1-2 周）— 核心链路跑通

| 里程碑 | 时间节点 | 交付物（可验证） | Agent | 验收标准 |
|--------|---------|-----------------|-------|---------|
| M1.1 骨架搭建 | Day 1 | 项目目录结构 + requirements.txt + `python -m voiceime` 入口可运行（打印版本号退出） | A+B | 运行不报错，目录结构与架构文档一致 |
| M1.2 基础设施 | Day 1-2 | ConfigManager + paths + log + single_instance | A | 配置读写正常；JSON 损坏时自动恢复为默认值；互斥体防多实例 |
| M1.3 模型管理 | Day 2-3 | ModelManager + downloader（HuggingFace 断点续传） | A | 首次运行下载模型，二次运行跳过；校验文件完整性 |
| M1.4 热键 + 录音 | Day 2-4 | HotkeyManager + Recorder（sounddevice 16kHz Mono） | B | Caps Lock keydown/keyup 事件触发；录音生成 numpy array；设备热插拔检测 |
| M1.5 ASR 推理 | Day 3-5 | ASREngine（faster-whisper large-v3-turbo int8 CPU） | B | 5s 音频推理返回非空 text；VAD 裁剪首尾静音；30s 超时触发错误 |
| M1.6 文本上屏 | Day 3-5 | OutputController（clipboard + uia + keyboard 三层） | B | 剪贴板备份→写入→Ctrl+V→恢复流程正常；记事本中粘贴成功 |
| M1.7 系统托盘 | Day 3-4 | SystemTray（pystray 4 状态图标 + 右键菜单） | A | 托盘图标显示；右键菜单可点击；退出清理钩子 |
| M1.8 集成联调 | Day 5-7 | CoreController 串联全部 P0 模块 | B | Caps Lock → 录音 → 松开 → 识别 → 上屏全链路跑通 |
| M1.9 首次引导 | Day 5-6 | FirstRunWizard（麦克风检测 + 模型下载 + 热键确认） | A | 首次启动引导完成，模型加载成功 |
| M1.10 基础设置 | Day 6-7 | SettingsWindow 推理引擎 Tab（模型/量化/VAD 配置） | A | 修改配置保存后生效；重启加载新配置 |
| M1.11 MVP 打包 | Day 7-10 | PyInstaller 单文件可执行 | A+B | 全新 Windows 机器双击运行，完成首次引导后可正常使用 |

## Phase 2 · 体验完善（2-3 周）

| 里程碑 | 时间节点 | 交付物（可验证） | Agent | 验收标准 |
|--------|---------|-----------------|-------|---------|
| M2.1 悬浮条 UI | Day 1-4 | FloatingBar（录音条 + 结果条 + 波形动画） | A | 热键按下 < 50ms 显示录音条；TopMost 不抢焦点；波形实时更新 |
| M2.2 标点后处理 | Day 2-3 | PostProcessPipeline（punct + converter + hotword） | B | "你好,世界." → "你好，世界。"; 繁简转换正确；热词替换命中 |
| M2.3 LLM 集成 | Day 3-6 | LLMClient + KeyringStore + LLM 设置 Tab | A+B | API Key 加密存储；润色调用返回书面语；10s 超时保留原文 |
| M2.4 历史记录 | Day 5-8 | HistoryRepo + HistoryWindow（搜索 + 过滤 + 再次上屏） | A | SQLite 读写正常；搜索 300ms 内返回；按应用过滤正确 |
| M2.5 热词词库 | Day 5-7 | HotwordRepo + HotwordWindow（CRUD + CSV 导入导出） | A | 增删改查实时生效；CSV 导入去重；小写匹配正确 |
| M2.6 完整设置 | Day 7-10 | SettingsWindow 5 Tab 全部实现 | A | 推理引擎/热键/后处理/LLM/高级 Tab 全部可交互并持久化 |
| M2.7 内存锁定 | Day 8-9 | VirtualLock 内存锁定 + 30s 心跳 | B | 模型常驻内存，二次唤醒 < 100ms；锁定上限可调 |
| M2.8 Phase 2 集成 | Day 10-14 | 全部 P1 功能联调 + 冒烟测试 | A+B | 悬浮条完整交互：录音→识别→后处理→确认/润色→上屏→历史记录 |

## Phase 3 · 智能化（1-2 周）

| 里程碑 | 时间节点 | 交付物（可验证） | Agent | 验收标准 |
|--------|---------|-----------------|-------|---------|
| M3.1 Vulkan 评估 | Day 1-3 | whisper.cpp Vulkan 780M benchmark 报告 | B | 5s 音频 ≤ 1.5s 则集成；不达标继续 CPU 方案并记录原因 |
| M3.2 上下文感知 | Day 3-5 | ContextEngine + context_rules.json + 规则编辑 UI | A+B | VSCode 中自动切换代码注释 Prompt；微信中自动快速上屏 |
| M3.3 性能验收 | Day 4-7 | 全量性能测试报告 | B | 模型冷启动 ≤ 8s；推理 ≤ 2.5s；内存 ≤ 4GB；待机 CPU < 1% |
| M3.4 最终发布 | Day 7-10 | PyInstaller 最终版 + 用户文档 | A+B | 全新机器安装后所有 P0+P1 功能可用；无 console 窗口 |

---

# 4 Agent 任务分配

## Agent A · infra-agent（基础设施 + UI）

**职责**：项目骨架、配置管理、数据持久化、模型管理、全部 UI 组件、打包分发。

### Agent A 独占文件

```
voiceime/__init__.py
voiceime/__main__.py           (仅入口骨架，CoreController 实例化归 Agent B)
voiceime/utils/paths.py
voiceime/utils/log.py
voiceime/utils/single_instance.py
voiceime/config/__init__.py
voiceime/config/defaults.py
voiceime/config/manager.py
voiceime/keyring/__init__.py
voiceime/keyring/store.py
voiceime/hotword/__init__.py
voiceime/hotword/repository.py
voiceime/history/__init__.py
voiceime/history/repository.py
voiceime/model/__init__.py
voiceime/model/manager.py
voiceime/model/downloader.py
voiceime/ui/__init__.py
voiceime/ui/tray.py
voiceime/ui/floating.py
voiceime/ui/settings.py
voiceime/ui/history_window.py
voiceime/ui/hotword_window.py
voiceime/ui/wizard.py
voiceime/ui/resources/icons/*    (托盘图标)
voiceime/ui/resources/styles/*   (QSS 样式)
```

### Agent A 禁止修改

```
voiceime/hotkey/*
voiceime/recorder/*
voiceime/asr/*
voiceime/postprocess/*
voiceime/output/*
voiceime/llm/*
voiceime/context/*
voiceime/core.py
```

### Agent A 任务清单

```json
[
  {
    "agent_id": "infra-agent",
    "responsibility": "基础设施、数据持久化、模型管理、UI、打包",
    "tasks": [
      {
        "id": "A001",
        "title": "创建项目骨架和目录结构",
        "milestone": "M1.1",
        "files_owned": [
          "voiceime/__init__.py",
          "voiceime/__main__.py",
          "requirements.txt",
          "setup.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "目录结构与 Architecture.md §9 一致",
          "python -m voiceime 可运行（打印版本号退出）",
          "requirements.txt 包含全部 P0 依赖"
        ],
        "depends_on": []
      },
      {
        "id": "A002",
        "title": "实现 utils 基础工具（paths/log/single_instance）",
        "milestone": "M1.2",
        "files_owned": [
          "voiceime/utils/__init__.py",
          "voiceime/utils/paths.py",
          "voiceime/utils/log.py",
          "voiceime/utils/single_instance.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "paths.data_dir 返回 %APPDATA%\\VoiceIME\\",
          "paths.ensure_dirs() 自动创建不存在的子目录",
          "single_instance 第二次启动检测到互斥体后退出"
        ],
        "depends_on": ["A001"]
      },
      {
        "id": "A003",
        "title": "实现 ConfigManager（config.json 读写 + 损坏恢复）",
        "milestone": "M1.2",
        "files_owned": [
          "voiceime/config/__init__.py",
          "voiceime/config/defaults.py",
          "voiceime/config/manager.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "config.get('asr.model') 返回 'large-v3-turbo'",
          "config.set('asr.vad_filter', False) 立即持久化",
          "手动损坏 config.json 后 reload 自动恢复为默认值",
          "线程安全：RLock 保护读写"
        ],
        "depends_on": ["A002"]
      },
      {
        "id": "A004",
        "title": "实现 ModelManager（模型下载/校验/版本管理）",
        "milestone": "M1.3",
        "files_owned": [
          "voiceime/model/__init__.py",
          "voiceime/model/manager.py",
          "voiceime/model/downloader.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "ensure_model('large-v3-turbo', 'int8') 返回模型目录 Path",
          "首次调用触发 HuggingFace 下载，二次调用跳过",
          "verify_model 检测 model.bin + config.json + vocabulary.txt 三文件",
          "下载失败重试 3 次",
          "下载进度通过 callback 回调"
        ],
        "depends_on": ["A003"]
      },
      {
        "id": "A005",
        "title": "实现 SystemTray（pystray 托盘图标 + 右键菜单）",
        "milestone": "M1.7",
        "files_owned": [
          "voiceime/ui/__init__.py",
          "voiceime/ui/tray.py",
          "voiceime/ui/resources/icons/green.png",
          "voiceime/ui/resources/icons/yellow.png",
          "voiceime/ui/resources/icons/red.png",
          "voiceime/ui/resources/icons/gray.png"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "托盘图标显示 4 种状态（绿/黄/红/灰）",
          "右键菜单包含：状态栏、LLM 润色开关、历史记录、设置、暂停、退出",
          "退出时托盘图标消失 + 钩子清理",
          "pystray 运行在独立线程，不阻塞 PyQt6 主循环"
        ],
        "depends_on": ["A003"]
      },
      {
        "id": "A006",
        "title": "实现 FirstRunWizard（首次启动引导）",
        "milestone": "M1.9",
        "files_owned": [
          "voiceime/ui/wizard.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "步骤 1：麦克风设备检测，无设备时禁用下一步",
          "步骤 2：模型下载进度条（复用 ModelManager）",
          "步骤 3：热键确认（显示 Caps Lock 说明 + 更换入口）",
          "完成后模型开始加载，引导窗口关闭"
        ],
        "depends_on": ["A004"]
      },
      {
        "id": "A007",
        "title": "实现 SettingsWindow 推理引擎 Tab",
        "milestone": "M1.10",
        "files_owned": [
          "voiceime/ui/settings.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "推理引擎 Tab：模型下拉、量化选择、VAD 开关/阈值滑块",
          "保存按钮写入 config.json 并生效",
          "恢复默认按钮重置当前 Tab 为默认值"
        ],
        "depends_on": ["A003", "A005"]
      },
      {
        "id": "A008",
        "title": "实现 KeyringStore（API Key 加密存储）",
        "milestone": "M2.3",
        "files_owned": [
          "voiceime/keyring/__init__.py",
          "voiceime/keyring/store.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "save_key('openai', 'sk-xxx') 写入 Windows Credential Manager",
          "get_key('openai') 返回明文 Key",
          "delete_key('openai') 清除存储",
          "config.json 中不包含明文 API Key"
        ],
        "depends_on": ["A003"]
      },
      {
        "id": "A009",
        "title": "实现 HotwordRepo（hotwords.json CRUD + CSV 导入导出）",
        "milestone": "M2.5",
        "files_owned": [
          "voiceime/hotword/__init__.py",
          "voiceime/hotword/repository.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "add/save/delete 立即持久化到 hotwords.json",
          "find('你尼达') 返回替换词 'UniData'（小写匹配）",
          "import_csv 去重并返回导入条数",
          "export_csv 生成两列格式文件"
        ],
        "depends_on": ["A003"]
      },
      {
        "id": "A010",
        "title": "实现 HistoryRepo（SQLite CRUD + 搜索 + 过滤）",
        "milestone": "M2.4",
        "files_owned": [
          "voiceime/history/__init__.py",
          "voiceime/history/repository.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "save 插入记录返回 id",
          "search('关键词') 300ms 内返回结果（1000 条数据基准）",
          "search(app_filter='Code.exe') 按应用过滤",
          "PRAGMA integrity_check 失败时自动备份 .bak + 重建"
        ],
        "depends_on": ["A003"]
      },
      {
        "id": "A011",
        "title": "实现 FloatingBar（悬浮录音条 + 结果确认条 + 波形）",
        "milestone": "M2.1",
        "files_owned": [
          "voiceime/ui/floating.py",
          "voiceime/ui/resources/styles/floating.qss"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "录音条 TopMost 不抢焦点，显示红色指示点 + 波形 + 时长",
          "结果条显示识别文本 + 语言 + 耗时 + 窗口名",
          "按钮：上屏(Enter) / 润色(Alt+E) / 重录(R) / 取消(Esc)",
          "热键按下到录音条显示 < 50ms",
          "快速模式下识别完成直接上屏，不显示结果条"
        ],
        "depends_on": ["A005"]
      },
      {
        "id": "A012",
        "title": "实现 HotwordWindow + HistoryWindow",
        "milestone": "M2.4",
        "files_owned": [
          "voiceime/ui/hotword_window.py",
          "voiceime/ui/history_window.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "HotwordWindow：表格展示 + 搜索 + 新增/编辑弹窗 + 删除确认 + CSV 导入导出",
          "HistoryWindow：按时间倒序 + 搜索 300ms debounce + 应用过滤下拉 + 再次上屏按钮",
          "两个窗口独立于主设置窗口，可同时打开"
        ],
        "depends_on": ["A009", "A010"]
      },
      {
        "id": "A013",
        "title": "完善 SettingsWindow 全部 5 个 Tab",
        "milestone": "M2.6",
        "files_owned": [
          "voiceime/ui/settings.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "推理引擎 Tab：模型/量化/VAD 配置",
          "热键配置 Tab：热键更换 + 快捷键说明",
          "后处理 Tab：标点/繁简/热词开关",
          "LLM 接口 Tab：服务商选择 + API Key 输入(加密) + 测试连接 + Prompt",
          "高级 Tab：内存锁定/剪贴板延迟/日志级别/录音时长",
          "每个 Tab 保存按钮 + 恢复默认按钮"
        ],
        "depends_on": ["A007", "A008"]
      },
      {
        "id": "A014",
        "title": "实现 ContextEngine（P2 窗口检测 + 规则匹配）",
        "milestone": "M3.2",
        "files_owned": [
          "voiceime/context/__init__.py",
          "voiceime/context/engine.py",
          "voiceime/context/window.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "get_foreground_window() 返回进程名 + 窗口标题",
          "match_rules() 返回匹配的行为覆盖（quick_mode/polish_mode/system_prompt）",
          "内置规则：VSCode→代码注释/WeChat→快速上屏/Word→商务书面语"
        ],
        "depends_on": ["A003"]
      },
      {
        "id": "A015",
        "title": "PyInstaller 打包 + 最终发布",
        "milestone": "M1.11",
        "phase_override": "M3.4",
        "files_owned": [
          "voiceime.spec",
          "scripts/build.ps1"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "单文件 .exe 双击运行，无 console 窗口",
          "包含托盘图标资源文件",
          "全新 Windows 11 机器无需安装 Python 即可运行",
          "首次运行自动创建 %APPDATA%\\VoiceIME\\ 目录结构"
        ],
        "depends_on": ["A006", "A013"]
      }
    ]
  }
]
```

## Agent B · pipeline-agent（核心管线）

**职责**：热键监听、音频录制、ASR 推理、文本后处理、文本上屏、LLM 调用、CoreController 编排。

### Agent B 独占文件

```
voiceime/hotkey/__init__.py
voiceime/hotkey/manager.py
voiceime/hotkey/hook.py
voiceime/recorder/__init__.py
voiceime/recorder/device.py
voiceime/recorder/stream.py
voiceime/asr/__init__.py
voiceime/asr/engine.py
voiceime/asr/memory.py
voiceime/postprocess/__init__.py
voiceime/postprocess/pipeline.py
voiceime/postprocess/punct.py
voiceime/postprocess/converter.py
voiceime/postprocess/hotword.py
voiceime/output/__init__.py
voiceime/output/controller.py
voiceime/output/clipboard.py
voiceime/output/uia.py
voiceime/output/keyboard.py
voiceime/llm/__init__.py
voiceime/llm/client.py
voiceime/llm/prompts.py
voiceime/core.py
```

### Agent B 禁止修改

```
voiceime/utils/*
voiceime/config/*
voiceime/keyring/*
voiceime/hotword/*
voiceime/history/*
voiceime/model/*
voiceime/ui/*
voiceime/__init__.py
voiceime/__main__.py
```

### Agent B 任务清单

```json
[
  {
    "agent_id": "pipeline-agent",
    "responsibility": "核心音频-推理-上屏管线、后处理、LLM、CoreController 编排",
    "tasks": [
      {
        "id": "B001",
        "title": "实现 HotkeyManager（pynput 全局钩子 + keydown/keyup 分发）",
        "milestone": "M1.4",
        "files_owned": [
          "voiceime/hotkey/__init__.py",
          "voiceime/hotkey/manager.py",
          "voiceime/hotkey/hook.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "Caps Lock keydown 触发 on_keydown 回调",
          "Caps Lock keyup 触发 on_keyup 回调",
          "录音期间 Caps Lock 灯不切换",
          "热键冲突检测：已被占用时抛出 HotkeyConflictError",
          "stop() 注销钩子 + atexit 注册清理",
          "事件通过 hotkey_queue 发送 HotKeyEvent"
        ],
        "depends_on": ["A001"]
      },
      {
        "id": "B002",
        "title": "实现 Recorder（sounddevice 16kHz Mono + ring buffer）",
        "milestone": "M1.4",
        "files_owned": [
          "voiceime/recorder/__init__.py",
          "voiceime/recorder/device.py",
          "voiceime/recorder/stream.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "start_recording 启动 sounddevice.InputStream 16kHz Mono float32",
          "回调内仅 ring_buffer.write(data)，零阻塞",
          "stop_recording 返回完整 numpy array + duration_ms",
          "录音 < 200ms 视为误触，返回空数据",
          "录音 ≥ 60s 自动停止",
          "设备断开时抛出 DeviceDisconnectedError",
          "device.list_devices() 返回可用麦克风列表"
        ],
        "depends_on": ["A001"]
      },
      {
        "id": "B003",
        "title": "实现 ASREngine（faster-whisper + VAD + 超时）",
        "milestone": "M1.5",
        "files_owned": [
          "voiceime/asr/__init__.py",
          "voiceime/asr/engine.py",
          "voiceime/asr/memory.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "load_model 加载 large-v3-turbo int8 CPU 模型（通过 CONTRACT-08 获取模型路径）",
          "transcribe 返回 ASRResult(text, language, inference_ms, segments)",
          "vad_filter=True 自动裁剪首尾静音",
          "推理超时 30s 抛出 InferenceTimeoutError",
          "推理在 ThreadPoolExecutor(max_workers=1) 中串行执行",
          "结果通过 result_queue 回传"
        ],
        "depends_on": ["A003", "A004", "B002"]
      },
      {
        "id": "B004",
        "title": "实现 OutputController（三层 Fallback 上屏）",
        "milestone": "M1.6",
        "files_owned": [
          "voiceime/output/__init__.py",
          "voiceime/output/controller.py",
          "voiceime/output/clipboard.py",
          "voiceime/output/uia.py",
          "voiceime/output/keyboard.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "clipboard: backup→write→Ctrl+V→Sleep(50ms)→restore",
          "clipboard 备份失败时跳过恢复（日志告警）",
          "clipboard 恢复失败时文本保留在剪贴板",
          "uia: 检测目标控件 Value Pattern 可用则注入",
          "keyboard: pyautogui 逐字符输入兜底",
          "output() 返回 OutputResult(success, method, error)"
        ],
        "depends_on": ["A003"]
      },
      {
        "id": "B005",
        "title": "实现 CoreController（全局编排 + 状态机）",
        "milestone": "M1.8",
        "files_owned": [
          "voiceime/core.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "状态机：READY → RECORDING → INFERRING → CONFIRMING → OUTPUTTING → READY",
          "QTimer 50ms 轮询 hotkey_queue + cmd_queue + result_queue + llm_queue",
          "热键 keydown → 调用 recorder.start()",
          "热键 keyup → 调用 recorder.stop() → asr.transcribe()",
          "ASR 结果 → postprocess → output → history.save",
          "快速模式跳过 CONFIRMING 直接 OUTPUTTING",
          "异常状态转换正确（ERROR_MIC / ERROR_MODEL / etc.）",
          "通过 pyqtSignal 通知 UI 状态变化"
        ],
        "depends_on": ["B001", "B002", "B003", "B004", "A003"]
      },
      {
        "id": "B006",
        "title": "实现 PostProcessPipeline（标点 + 繁简 + 热词替换）",
        "milestone": "M2.2",
        "files_owned": [
          "voiceime/postprocess/__init__.py",
          "voiceime/postprocess/pipeline.py",
          "voiceime/postprocess/punct.py",
          "voiceime/postprocess/converter.py",
          "voiceime/postprocess/hotword.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "punct: 英文逗号→中文逗号，移除句尾语气词",
          "converter: opencc 繁→简 / 简→繁转换",
          "hotword: 遍历热词表执行替换（通过 CONTRACT-06 HotwordProvider 获取词库）",
          "pipeline.process() 按顺序执行启用的步骤",
          "各步骤可独立开关（config 中配置）"
        ],
        "depends_on": ["A003"]
      },
      {
        "id": "B007",
        "title": "实现 LLMClient（Claude/OpenAI/Ollama + 超时 + 取消）",
        "milestone": "M2.3",
        "files_owned": [
          "voiceime/llm/__init__.py",
          "voiceime/llm/client.py",
          "voiceime/llm/prompts.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "支持 Claude API / OpenAI API / Ollama 三种后端切换",
          "polish() 调用 LLM API，10s 超时",
          "DNS 解析超时 5s",
          "cancel() 取消进行中的请求",
          "未配置 API Key 时 is_configured=False",
          "结果通过 llm_queue 回传 LLMResult"
        ],
        "depends_on": ["A008"]
      },
      {
        "id": "B008",
        "title": "集成 LLM 润色到 PostProcessPipeline",
        "milestone": "M2.3",
        "files_owned": [
          "voiceime/postprocess/pipeline.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "polish_only() 仅调用 LLM 润色",
          "LLM 超时/失败时返回原文 + is_polished=False",
          "自动润色模式：识别完成后自动触发",
          "手动润色模式：用户点击按钮触发"
        ],
        "depends_on": ["B006", "B007"]
      },
      {
        "id": "B009",
        "title": "实现 VirtualLock 内存锁定 + 心跳",
        "milestone": "M2.7",
        "files_owned": [
          "voiceime/asr/memory.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "lock_model_memory(ptr, size) 调用 VirtualLock 锁定物理内存",
          "锁定上限 3.5GB，超出部分不锁定",
          "30s 心跳读取模型元数据维持活跃",
          "unlock_model_memory() 释放锁定",
          "提供开关（config.ui.memory_lock）"
        ],
        "depends_on": ["B003"]
      },
      {
        "id": "B010",
        "title": "Vulkan 加速 benchmark（whisper.cpp）",
        "milestone": "M3.1",
        "files_owned": [],
        "files_forbidden": [],
        "acceptance_criteria": [
          "编译 whisper.cpp Vulkan 后端",
          "5s 音频推理耗时记录",
          "与 CPU faster-whisper 对比报告",
          "达标(≤1.5s)则输出集成方案；不达标则记录原因"
        ],
        "depends_on": ["B003"]
      },
      {
        "id": "B011",
        "title": "集成 ContextEngine 到 CoreController",
        "milestone": "M3.2",
        "files_owned": [
          "voiceime/core.py"
        ],
        "files_forbidden": [],
        "acceptance_criteria": [
          "识别前读取当前焦点窗口信息（通过 CONTRACT ContextEngine）",
          "匹配规则后覆盖 postprocess 行为和 LLM Prompt",
          "无匹配时使用全局默认设置"
        ],
        "depends_on": ["A014", "B008"]
      },
      {
        "id": "B012",
        "title": "全量性能验收测试",
        "milestone": "M3.3",
        "files_owned": [],
        "files_forbidden": [],
        "acceptance_criteria": [
          "模型冷启动 ≤ 8s (SSD)",
          "二次唤醒 < 100ms (VirtualLock 后)",
          "5s 音频推理 ≤ 2.5s (CPU int8)",
          "内存占用 ≤ 4GB",
          "待机 CPU < 1%",
          "输出完整性能测试报告"
        ],
        "depends_on": ["B009"]
      }
    ]
  }
]
```

---

# 5 共享 Protocol 定义文件

> 两个 Agent 共同依赖的接口定义，双方均不可单方面修改。
> 文件路径：`voiceime/protocols.py`（需 Agent A 在 M1.1 骨架中创建）

```python
# voiceime/protocols.py
# 接口契约的 Python Protocol 定义，两个 Agent 共同引用
# 修改此文件需双方确认

from typing import Protocol, Callable, Any
from pathlib import Path
from collections import namedtuple
from dataclasses import dataclass
import numpy as np


# ── Data Types ──────────────────────────────────────

HotKeyEvent = namedtuple('HotKeyEvent', ['key', 'action'])

AudioData = namedtuple('AudioData', ['pcm', 'duration_ms', 'sample_rate'])

DeviceInfo = namedtuple('DeviceInfo', ['id', 'name', 'is_default'])

ASRResult = namedtuple('ASRResult', [
    'text', 'language', 'inference_ms', 'segments'
])

ProcessContext = namedtuple('ProcessContext', ['app_name', 'app_title'])

ProcessResult = namedtuple('ProcessResult', [
    'text', 'is_polished', 'steps_applied'
])

OutputResult = namedtuple('OutputResult', ['success', 'method', 'error'])

LLMResult = namedtuple('LLMResult', ['text', 'is_success', 'error'])

DownloadProgress = namedtuple('DownloadProgress', [
    'downloaded_bytes', 'total_bytes', 'speed_bps', 'eta_seconds'
])


@dataclass
class HistoryRecord:
    id: int | None = None
    created_at: str = ''
    text: str = ''
    raw_text: str | None = None
    language: str | None = None
    app_name: str | None = None
    app_title: str | None = None
    audio_duration_ms: int | None = None
    inference_time_ms: int | None = None
    is_polished: bool = False


# ── Protocol Interfaces ─────────────────────────────

class ConfigProvider(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def reload(self) -> None: ...
    @property
    def data_dir(self) -> Path: ...


class HotkeyProvider(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def set_callback(self, on_keydown: Callable[[], None],
                     on_keyup: Callable[[], None]) -> None: ...
    @property
    def current_hotkey(self) -> str: ...


class AudioProvider(Protocol):
    def start_recording(self) -> None: ...
    def stop_recording(self) -> AudioData: ...
    @property
    def is_recording(self) -> bool: ...
    @property
    def duration_ms(self) -> int: ...
    @property
    def devices(self) -> list[DeviceInfo]: ...


class ASRProvider(Protocol):
    def load_model(self) -> None: ...
    def transcribe(self, audio: np.ndarray) -> ASRResult: ...
    @property
    def is_loaded(self) -> bool: ...
    def unload_model(self) -> None: ...


class PostProcessProvider(Protocol):
    def process(self, text: str,
                context: ProcessContext | None = None) -> ProcessResult: ...
    def polish_only(self, text: str,
                    context: ProcessContext | None = None) -> ProcessResult: ...


class OutputProvider(Protocol):
    def output(self, text: str) -> OutputResult: ...


class HistoryProvider(Protocol):
    def save(self, record: HistoryRecord) -> int: ...
    def search(self, query: str, app_filter: str | None = None,
               limit: int = 50, offset: int = 0) -> list[HistoryRecord]: ...
    def delete(self, record_id: int) -> bool: ...
    def clear_all(self) -> int: ...
    @property
    def total_count(self) -> int: ...


class ModelProvider(Protocol):
    def ensure_model(self, model_name: str, quantization: str) -> Path: ...
    def verify_model(self, model_dir: Path) -> bool: ...
    @property
    def download_progress(self) -> DownloadProgress | None: ...
    @property
    def available_models(self) -> list[str]: ...


class LLMProvider(Protocol):
    def polish(self, text: str, system_prompt: str | None = None) -> LLMResult: ...
    def cancel(self) -> None: ...
    def test_connection(self) -> bool: ...
    @property
    def is_configured(self) -> bool: ...


class HotwordProvider(Protocol):
    def find(self, trigger: str) -> str | None: ...
    def list_all(self) -> list[dict]: ...
```

---

# 6 Agent 协作规范

## 6.1 通信协议

| 场景 | 方式 |
|------|------|
| 日常进度 | 各自在任务文件中推进，通过 git commit 同步 |
| 接口变更 | 修改 `voiceime/protocols.py` 前必须通知对方，双方确认后才可提交 |
| 阻塞上报 | 在 commit message 或 TODO 中标记 `BLOCKED-BY: {task_id}` |
| 集成问题 | M1.8 / M2.8 联调阶段集中解决 |

## 6.2 Git 分支策略

```
main
├── feat/infra-A001-skeleton        Agent A 任务分支
├── feat/infra-A003-config          Agent A 任务分支
├── feat/pipeline-B001-hotkey       Agent B 任务分支
├── feat/pipeline-B003-asr          Agent B 任务分支
└── ...
```

- 每个任务对应一个 `feat/` 分支
- 完成后 PR 合并到 `main`
- `protocols.py` 变更必须走 PR 审查

## 6.3 文件冲突避免

两个 Agent 的 `files_owned` 和 `files_forbidden` 严格互补，**唯一共享文件**：
- `voiceime/protocols.py`：双方引用，修改需双方确认
- `voiceime/__main__.py`：Agent A 拥有入口骨架，Agent B 负责 CoreController 实例化逻辑

---

# 7 风险与缓解

| 风险 | 触发条件 | 影响 | 缓解 |
|------|---------|------|------|
| CPU 推理不达标 | 5s 音频 > 2.5s | 核心体验差 | M1.5 完成后立即 benchmark；不达标则降级模型或提前启动 M3.1 Vulkan 评估 |
| pystray + PyQt6 冲突 | 两个事件循环互相阻塞 | 托盘或 UI 卡死 | M1.7 专项验证；备选 QSystemTrayIcon |
| 剪贴板竞争 | 50ms 内用户手动复制 | 原内容丢失 | 提供关闭开关；实测主流应用调整延迟 |
| 热键冲突 | Caps Lock 被其他程序占用 | 无法录音 | 提供热键更换入口 + 启动时检测告警 |
| 模型下载失败 | HuggingFace 网络不通 | 无法使用 | 断点续传 + 3 次重试 + 提示手动下载地址 |

---

# 开发编排摘要（供下游 Skill 05/06 优先读取，≤300字）

> 2 Agent 并行开发。Agent A (infra-agent)：项目骨架、ConfigManager、ModelManager、全部 UI（tray/floating/settings/wizard/history/hotword）、KeyringStore、HistoryRepo、HotwordRepo、打包分发。Agent B (pipeline-agent)：HotkeyManager、Recorder、ASREngine、PostProcessPipeline、OutputController、LLMClient、CoreController、ContextEngine(P2)。
> 关键路径：config → model → asr → core → output。
> 唯一共享文件 voiceime/protocols.py 定义全部 Protocol 接口，双方通过接口契约解耦。
> Phase 1 MVP 7-10 天（核心链路跑通）；Phase 2 体验 10-14 天（悬浮条+后处理+LLM+历史+热词）；Phase 3 智能化 7-10 天（Vulkan+上下文感知+性能验收）。
> 最大风险：CPU 推理性能待实测，M1.5 完成后立即验证。
