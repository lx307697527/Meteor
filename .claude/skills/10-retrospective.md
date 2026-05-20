# Skill 10 · Retrospective（会话回顾与规则进化）

## 触发时机
- 用户说 `/retrospective` 或 "回顾一下"
- 会话结束前（Stop hook 触发时可选执行）
- 里程碑完成后主动建议

## 角色行为准则

你的判断标准是：**这次会话中发生了哪些「应该被记住但还没被记住」的事？**

- 不回顾已完成的工作（用户能看 git log），只关注「下次应该怎样不同」。
- 区分「一次性事件」和「系统性问题」——只有后者值得变成规则。
- 回顾产出必须是可操作的：新规则、规则晋升、规则归档。

---

## Workflow

**Step 1 · 事件扫描**
读取项目 memory 中的 incidents.md，找出本会话新增的、标记为 `[待分析]` 的事件。

**Step 2 · 去重检查**
对每个待分析事件，检查现有规则是否已覆盖：
- 扫描 `CLAUDE.md` 硬约束表
- 扫描 `.claude/rules/*.md`
- 扫描 `.claude/agent.md` 踩坑清单

**Step 3 · 规则提炼**
对未被覆盖的系统性问题：

| 严重度 | 判断标准 | 动作 |
|--------|----------|------|
| P0 关键 | 违反即 Bug / 数据丢失 / 安全漏洞 | 立即写入 `.claude/rules/{topic}.md` |
| P1 重要 | 影响开发效率 / 重复犯错 ≥2 次 | 草拟到 `.claude/rules/draft-{topic}.md` |
| P2 观察 | 单次发生、可能偶发 | 记录在 memory，标记观察 |

**Step 4 · 规则淘汰检查**
扫描 `.claude/rules/` 中所有规则文件：
- 上次触发时间 > 10 个会话 → 建议归档
- 与 CLAUDE.md 内容重复 → 合并或删除
- 规则文件 > 30 行 → 拆分

**Step 5 · 进化报告**

输出格式：

```markdown
## 会话进化报告 [日期]

### 新增规则
- [.claude/rules/{topic}.md] 一句话描述规则内容

### 草拟规则
- [.claude/rules/draft-{topic}.md] 待验证：一句话描述

### 规则晋升
- [draft-X → rules/Y] 理由：预防了 N 次问题

### 建议归档
- [rules/Z] 理由：N 个会话未触发

### 待观察事件
- memory/incidents.md 中标记为 P2 的事件列表

### 统计
- 活跃规则数：X | 草拟规则数：Y | 本会话新增事件：Z
```

---

## 交付契约

```
→ 输出：进化报告（Markdown）+ 规则文件变更（如有）
→ 副作用：可修改 .claude/rules/、memory/incidents.md、CLAUDE.md
→ 不修改：任何 src/ 下的代码文件
```
