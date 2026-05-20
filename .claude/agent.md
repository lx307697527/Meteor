# VoiceIME Agent 防翻车手册

> 本文档由 PRD 和技术选型提炼，Agent 编写或修改代码前必须逐条自检。

---

## 一、编码前必检（3 秒速查）

写代码前对照此表，命中任何一条即需特别处理：

| # | 检查项 | 命中标志 | 正确做法 |
|---|---|---|---|
| 1 | 是否修改全局键盘钩子逻辑？ | 涉及 `pynput`/`WH_KEYBOARD_LL` | 确认 Caps Lock 拦截后系统默认行为是否被正确抑制，退出时必须注销钩子 |
| 2 | 是否操作剪贴板？ | 调用 `pyperclip`/`win32clipboard` | 必须先备份原内容，上屏后 50ms 内恢复，异常时记录日志不静默丢失 |
| 3 | 是否涉及 Whisper 模型加载/推理？ | 调用 `faster_whisper`/`WhisperModel` | 确认模型路径存在，内存锁定（VirtualLock）开关是否生效，推理超时 30s 兜底 |
| 4 | 是否新增音频录制参数？ | 修改 `sounddevice` 采样率/声道/格式 | 固定 16kHz/Mono/float32，禁止随意更改，Whisper 输入格式硬性要求 |
| 5 | 是否涉及 UIAutomation 文本注入？ | 调用 `pywinauto`/`uia` | 必须先检测 Value Pattern 是否可用，不可用时降级到剪贴板方案 |
| 6 | 是否存储 API Key？ | 读写 LLM 服务商密钥 | 必须使用 `keyring` 存取 Windows Credential Manager，禁止写入 config.json 明文 |
| 7 | 是否涉及 VAD 参数？ | 修改 `vad_filter`/`vad_threshold` | 默认 vad_filter=True, threshold=0.5，修改后需重新测试中英文识别率 |
| 8 | 是否修改悬浮条 UI？ | 涉及 PyQt6/tkinter 窗口 | 确认 TopMost 置顶不抢焦点，Esc/Enter/R 快捷键响应正常 |

---

## 二、已知坑位登记

以下代码区域有预判风险，修改时需额外警惕：

| 模块 | 坑位描述 | 注意事项 |
|---|---|---|
| 全局热键 | Caps Lock 拦截后若进程崩溃，钩子不会自动释放 → Caps Lock 永久失效 | 必须注册 atexit 清理 + try/finally 双保险 |
| 剪贴板上屏 | 备份→写入→Ctrl+V→50ms→恢复，50ms 间隔在极端情况下用户可能操作剪贴板 | 此风险极低暂不处理，但恢复失败必须记日志 |
| 模型常驻 | Windows 内存分页会将长期无 I/O 的进程内存压缩至 Pagefile → 首次唤醒卡顿数秒 | VirtualLock + 30s 心跳访问，关闭开关供低内存场景让出 |
| 录音设备 | 麦克风热插拔/断开时 sounddevice 回调会抛异常 | 录音线程必须 try/except 包裹，断开时立即停止并在悬浮条提示 |
| Whisper 推理 | 模型文件损坏或缺失时直接崩溃 | 启动时检测模型文件完整性，异常时降级模式（无 ASR，仅托盘图标） |
| LLM 润色 | API 超时或网络异常时用户可能误以为卡死 | 10s 超时兜底，超时保留原文并显示「润色超时」提示 |
| 热词替换 | 触发词大小写不统一导致匹配失败 | 存储时统一转小写匹配 |

---

## 三、技术选型速查

| 模块 | 选型 | 关键约束 |
|---|---|---|
| 全局热键 | pynput | keydown/keyup 区分，Caps Lock 拦截需抑制系统默认行为 |
| 音频录制 | sounddevice + numpy | 16kHz / Mono / float32，直接输出 numpy array |
| VAD | faster-whisper 内置 Silero VAD | vad_filter=True, min_silence_duration_ms=300 |
| ASR 推理 | faster-whisper (CTranslate2) | large-v3-turbo, int8, CPU 后端，模型常驻内存 |
| 文本上屏 | pyperclip + pyautogui / pywinauto | 三层 Fallback: UIAutomation → 剪贴板+Ctrl+V → 逐字符 |
| 系统托盘 | pystray | 状态图标切换，右键菜单 |
| 设置窗口 | PyQt6 或 tkinter | PyQt6 更现代，tkinter 无需安装 |
| LLM 调用 | anthropic / openai SDK | 按配置切换，10s 超时 |
| 繁简转换 | opencc-python-reimplemented | 纯 Python，无 C++ 编译依赖 |
| 配置存储 | JSON (config.json) | %APPDATA%\VoiceIME\config.json |
| 历史记录 | SQLite (sqlite3) | 本地轻量，零依赖 |
| API Key | keyring (Windows Credential Manager) | 系统级加密，禁止明文 |

---

## 四、提交前 Checklist

```markdown
## 提交前自检（Agent 自动执行）

- [ ] `pytest` 全量通过
- [ ] 变更文件数 ≤ 10，变更行数 ≤ 500
- [ ] 无 print / TODO HACK / 临时脚本残留
- [ ] 若涉及新功能：PRD.md 已更新
- [ ] 若涉及架构变更：Architecture.md 已更新
- [ ] 若修改全局钩子：确认异常退出时钩子可正确注销
- [ ] 若操作剪贴板：确认备份恢复逻辑完备
- [ ] 若涉及 API Key：确认使用 keyring 而非明文存储
```

---

## 五、变更影响评估流程

修改任何已有函数/类/模块前：

1. 使用 `codegraph_impact` 评估影响范围
2. 若风险为 HIGH/CRITICAL，先向用户报告，取得确认后再修改
3. 修改后运行相关测试文件，确认未引入回归
4. 若修改涉及跨模块接口，同步检查消费方的适配
