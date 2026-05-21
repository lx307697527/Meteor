# TeacherCopilot 项目约束

> 详细规则见 `.claude/rules/`：[commit.md](.claude/rules/commit.md) [docs.md](.claude/rules/docs.md) [doc-sync.md](.claude/rules/doc-sync.md) [code-review.md](.claude/rules/code-review.md) [bug-tracking.md](.claude/rules/bug-tracking.md)

## 行为底线
- 信息不足先反问，禁止强行输出
- 不确定判断标注 [置信度: 低/中/高]
- 禁止伪造运行时数据

## 技术栈硬约束（违反即 Bug）

**Electron + CommonJS**：主进程必须 CommonJS，禁止 `"type": "module"`；原生模块改依赖后必须 `npm run rebuild`

**SQLite 单写者**：必须 `requestSingleInstanceLock()`；退出前 WAL checkpoint；文件写入用 write-then-rename

**AI 双路径**：PII 脱敏、合规校验、日志等横切关注点必须在流式/非流式两条路径同步实现

**React Hooks**：异步回调引用 DOM 必须用 `useRef`；`useEffect` 清理必须中断未完成异步操作

**IPC 安全**：preload 的 `on`/`off`/`once` 必须用频道白名单；新增频道必须同步更新白名单

## 配置与常量策略

禁止硬编码外部系统的返回值属性，必须动态获取或配置化：

| 禁止硬编码项 | 正确做法 | Bug 来源 |
|---|---|---|
| embedding 向量维度 | 从模型配置或首次响应推断 | `b4abb63` |
| API 端点路径 | `normalizeApiUrl()` 自动补全 | `7ef00b0` |
| 资源文件路径 | `app.isPackaged` 动态判断 | `ef961a3` |
| 设备指纹采集方式 | 检测 OS 版本选择方案 | `5132dc2` |
| PDF 解析 API 调用方式 | 检测库版本适配 | `dea8c0c` |

## 文档路径约定

| 文档 | 路径 |
|------|------|
| PRD | `docs/product/PRD.md` |
| TODO | `docs/product/TODO.md` |
| Architecture | `docs/architecture/Architecture.md` |
| DevOrchestration | `docs/engineering/DevOrchestration.md` |
| TestPlan | `docs/qa/TestPlan.md` |

## LLM Wiki（按需查阅，优先于源文档）

> 业务/设计上下文的压缩知识库，每个文件 ≤200 行。Agent 需求上下文时，
> 先读 `.claude/wiki/index.md` 路由到对应 digest，再按需读源文档补充细节。

| Digest | 查阅场景 |
|--------|---------|
| @.claude/wiki/prd-digest.md | 模块功能、合规规则、交互逻辑、流转关系 |
| @.claude/wiki/arch-digest.md | 数据模型、API契约、安全架构、技术栈 |
| @.claude/wiki/dev-digest.md | IPC契约、任务分配、里程碑、文件所有权 |
| @.claude/wiki/test-digest.md | 测试策略、验收标准、测试用例ID |

## 自动回顾
- 新会话首次交互时，读取 `memory/last-retrospective.md` 的时间戳
- 若距今超过 2 天，自动执行 Skill 10 回顾流程，完成后更新时间戳
- 若距今不超过 2 天，跳过

## Skill 索引

| # | Skill | 文件 |
|---|-------|------|
| 01 | 市场调研 | @.claude/skills/01-i2m.md |
| 02 | PRD 设计 | @.claude/skills/02-prd.md |
| 03 | 系统架构 | @.claude/skills/03-arch.md |
| 04 | 开发编排 | @.claude/skills/04-dev.md |
| 05 | QA 测试 | @.claude/skills/05-qa.md |
| 06 | 部署 SRE | @.claude/skills/06-deploy.md |
| 07 | 增长运营 | @.claude/skills/07-growth.md |
| 08 | 迭代演进 | @.claude/skills/08-iteration.md |
| 09 | 安全合规 | @.claude/skills/09-security.md |
| 10 | 会话回顾 | @.claude/skills/10-retrospective.md |

调用链：01 → 02 ↔ 09 → 03 → 04 → 05/06 → 07 → 08 → 回到 02
Skill 09 必须在 Skill 03 之前完成，禁止事后补审。
Skill 10 按需触发（`/retrospective`），不参与调用链，负责规则提炼与进化闭环。

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **TeacherCopilot** (3198 symbols, 4570 relationships, 126 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- **MUST run `vitest run` before committing** to confirm all tests pass.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.
<!-- gitnexus:end -->
