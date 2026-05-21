# Bug 历史记录

> 本文件记录所有已修复的 Bug，含根因分析、修复方式和关联规则。
> 修复 Bug 后必须同步更新本文件（规则来源：`.claude/rules/bug-tracking.md`）。

---

## 模板

```markdown
### BUG-NNN: [Bug 标题]

| 字段 | 内容 |
|------|------|
| 发现时间 | YYYY-MM-DD |
| 修复时间 | YYYY-MM-DD |
| 优先级 | P0/P1/P2 |
| 影响范围 | 受影响的模块/功能 |
| 根因 | 根因分析（Why，非 What） |
| 修复方式 | 具体改动描述 |
| 关联规则 | 关联 `.claude/rules/` 中的规则文件（如有） |
| 关联提交 | commit hash |
| 复现条件 | 触发该 Bug 的前置条件 |
| 预防措施 | 防止同类 Bug 再次发生的措施 |
```

---

## 记录

### BUG-001: 模型验证文件列表与实际文件名不匹配

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-05-21 |
| 修复时间 | 2026-05-21 |
| 优先级 | P0 |
| 影响范围 | 模型下载 + 模型验证：每次启动都重复下载 3GB 模型 |
| 根因 | `_REQUIRED_FILES` 写的是 `vocabulary.txt`，但 HuggingFace 上 Systran/faster-whisper 模型实际提供 `vocabulary.json`。`verify_model()` 因找不到 `vocabulary.txt` 永远返回 False，导致 `ensure_model()` 误判模型缺失触发重新下载。 |
| 修复方式 | 将 `downloader.py` 和 `manager.py` 中的 `_REQUIRED_FILES` 从 `vocabulary.txt` 改为 `vocabulary.json` |
| 关联规则 | 无（新发现模式） |
| 关联提交 | 待提交 |
| 复现条件 | 首次启动或模型已下载后重启，`verify_model()` 返回 False 触发重复下载 |
| 预防措施 | 外部系统文件清单必须从实际源验证，不能假设文件名 |

### BUG-002: ASR 推理线程池自死锁导致 30s 超时

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-05-21 |
| 修复时间 | 2026-05-21 |
| 优先级 | P0 |
| 影响范围 | 核心推理链路：按住说话松开后始终无文字上屏，状态卡在 INFERRING 直到超时 |
| 根因 | `CoreController._start_inference()` 将 `asr.transcribe()` 提交到 `ThreadPoolExecutor(max_workers=1)`。`transcribe()` 内部又向 **同一个池子** `submit(_do_transcribe)` 并等待 `future.result(timeout=30)`。唯一 worker 被 `transcribe()` 占用，`_do_transcribe` 无法入队执行 → 30s 后 `future.result()` 超时 → `_do_transcribe` 在 worker 释放后才执行，结果被丢弃。 |
| 修复方式 | `transcribe()` 改为直接同步调用 `_do_transcribe()`，不再经过 executor。超时检测移至 CoreController 轮询层（50ms 轮询 + 30s 超时阈值）。 |
| 关联规则 | 无（新发现模式） |
| 关联提交 | 待提交 |
| 复现条件 | 按下录音快捷键→松开→推理开始后等待 >30s→识别中状态消失但无文字上屏 |
| 预防措施 | `ThreadPoolExecutor(max_workers=1)` 禁止向自身递归提交任务。同步方法中不需要嵌套 executor。 |

### BUG-003: 设置保存后不生效（需重启）

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-05-21 |
| 修复时间 | 2026-05-21 |
| 优先级 | P1 |
| 影响范围 | 所有设置项：切换模型、热键、推理参数等保存后不生效 |
| 根因 | `_on_settings_closed()` 仅将 `_settings_window` 置为 None，没有检查哪些配置项变化并应用到运行中的模块。ConfigManager.set() 已将配置持久化到磁盘，但 CoreController 未读取新值。 |
| 修复方式 | 在 `_on_settings_closed()` 中检测 hotkey 和 model 是否变化，自动热重载对应模块（热键立即重启、模型异步卸载重载+下载）。Beam Size/语言/VAD 原本就是从 ConfigManager 实时读取，改完即生效。 |
| 关联规则 | 无（新发现模式） |
| 关联提交 | 待提交 |
| 复现条件 | 打开设置 → 修改模型/热键 → 确定 → 功能未变化 |
| 预防措施 | 设置窗口关闭时，CoreController 必须 diff 关键配置项并热重载受影响的模块。 |

### BUG-004: 进程被 kill 后命名互斥锁残留阻止重启

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-05-21 |
| 修复时间 | 2026-05-21 |
| 优先级 | P2 |
| 影响范围 | 单实例检测：开发过程中反复重启时，前一个进程被强制终止后无法启动新实例 |
| 根因 | `CreateMutexW` 检测到互斥锁已存在（ERROR_ALREADY_EXISTS）即拒绝启动，但未检查该锁是否来自已崩溃进程的废弃互斥体（WAIT_ABANDONED）。Windows 内核在拥有进程终止后标记互斥体为废弃但不自动销毁，新进程需通过 `WaitForSingleObject` 接管。 |
| 修复方式 | 在 `request_single_instance_lock()` 中遇到 ERROR_ALREADY_EXISTS 时，调用 `WaitForSingleObject(handle, 0)` 检查返回码。若为 WAIT_ABANDONED 则接管该锁，否则拒绝。 |
| 关联规则 | 无（新发现模式） |
| 关联提交 | 待提交 |
| 复现条件 | 运行 VoiceIME → taskkill 强制终止 → 立即再次启动 → 提示 "Another instance is already running" |
| 预防措施 | 命名互斥体检测需同时处理废弃状态。可考虑增加进程存活心跳验证。 |

### BUG-005: 模型加载时 faster-whisper 模块缺失

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-05-21 |
| 修复时间 | 2026-05-21 |
| 优先级 | P2 |
| 影响范围 | 全新环境首次运行：模型加载时报 `ModuleNotFoundError: No module named 'faster_whisper'` |
| 根因 | `requirements.txt` 虽已声明 `faster-whisper>=1.0`，但环境初始化时未执行 `pip install -r requirements.txt`（或部分依赖因编译失败跳过），导致运行时 import 失败。`asr/engine.py` 的 `load_model()` 延迟导入 `faster_whisper`，缺失时错误信息未提示用户运行安装命令。 |
| 修复方式 | `pip install faster-whisper` 手动安装，已验证 ctranslate2 4.7.2 + faster-whisper 1.2.1 兼容 |
| 关联规则 | 无 |
| 关联提交 | 待提交 |
| 复现条件 | 环境中未安装 faster-whisper 时启动 VoiceIME，模型加载阶段报错 |
| 预防措施 | 可考虑在入口处检查关键依赖并在缺失时给出明确的安装指引 |

### BUG-006: 错误态下快捷键无响应，用户需重启

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-05-21 |
| 修复时间 | 2026-05-21 |
| 优先级 | P1 |
| 影响范围 | 推理超时/模型错误后用户按快捷键无反应，只能右键退出重开 |
| 根因 | `_on_hotkey_down()` 仅允许 `READY` 态进入录音。错误态（ERROR_INFERENCE_TIMEOUT/ERROR_MODEL 等）静默忽略按键，用户无反馈。 |
| 修复方式 | 在 `_on_hotkey_down()` 入口处检测 `_ERROR_STATES`，先自动恢复 READY 再进入录音流程。 |
| 关联规则 | 无（新发现模式） |
| 关联提交 | 待提交 |
| 复现条件 | 推理超时 → 状态变为 ERROR_INFERENCE_TIMEOUT → 按快捷键无反应 |
| 预防措施 | 状态机需定义每个错误态的恢复路径，用户触发动作（快捷键）应能从错误态自救。 |

### BUG-007: 重复 addRow 导致 Qt 断言失败，设置窗口创建静默崩溃

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-05-21 |
| 修复时间 | 2026-05-21 |
| 优先级 | P1 |
| 影响范围 | 设置窗口：点击托盘"设置"无任何反应 |
| 根因 | `_UITab._setup_ui()` 中 `_hotkey_combo` 被 `addRow` 了两次到同一个 `QFormLayout`，Qt 运行时断言失败抛出异常。该异常被 `_poll_queues` 中的 `except: break` 静默吞掉，不记录日志、不提示用户。 |
| 修复方式 | 删除重复的 `addRow("录音快捷键：", self._hotkey_combo)` 行；将 `except: break` 改为 `logger.error(...)` 避免未来异常被静默吞掉 |
| 关联规则 | 无 |
| 关联提交 | 待提交 |
| 复现条件 | 打开设置窗口 → `SettingsWindow.__init__` → `_UITab.__init__` 因重复 addRow 抛出异常 → 窗口不显示，无任何提示 |
| 预防措施 | Qt 代码中同一 widget 不可重复 `addRow` 到同一布局；`_poll_queues` 的异常捕获必须至少记录日志 |

### BUG-008: `_on_settings_closed` 挂载到 `destroyed` 信号导致设置保存后模型不下载、热键不重载

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-05-22 |
| 修复时间 | 2026-05-22 |
| 优先级 | P1 |
| 影响范围 | 设置保存后热键/模型重载不生效；第二次点设置打不开窗口 |
| 根因 | (1) `_on_settings_closed()` 挂载到 `destroyed` 信号，但对话框点 OK 后只是隐藏而非销毁（`self._settings_window` 保持引用），`destroyed` 永不触发 → 重载逻辑永不运行。 (2) 第二次点设置时 `_settings_window is not None`（旧对话框对象仍存活但已隐藏），`raise_()` 对隐藏窗口无效 → 用户感觉点不动。 |
| 修复方式 | (1) 改用 `accepted` 信号触发重载逻辑，确保点 OK 时立刻执行。 (2) 添加 `WA_DeleteOnClose` 属性 + `destroyed` 信号清理引用，确保对话框关闭即销毁，下次打开创建新实例。 (3) `_open_settings` 对已有窗口先 `show()` 再 `raise_()` + `activateWindow()` 兜底。 |
| 关联规则 | 无 |
| 关联提交 | 待提交 |
| 复现条件 | 打开设置 → 切换模型/热键 → 确定 → 功能未变化；再点设置 → 窗口不弹出 |
| 预防措施 | QDialog 的 `destroyed` 信号在设计良好的引用持有下几乎不会触发，应优先使用 `accepted`/`rejected`/`finished` 信号处理保存后逻辑；非模态对话框用 `WA_DeleteOnClose`。 |
