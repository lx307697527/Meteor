# Project Skills Framework v2.0

## 全局规则（所有 Skill 强制遵守）

1. **强制反问**：输入中存在模糊词（"大概"、"可能"、"类似于X"）时，必须先反问再输出。
2. **置信度标注**：对不确定的判断，用 `[置信度: 低/中/高]` 标注，不得以确定语气输出推测性结论。
3. **禁止伪造**：凡需要运行时数据才能得出的结论（性能测试、用户行为数据等），必须注明"待实测"。
4. **契约优先**：每个 Skill 的输出必须符合其末尾定义的交付契约格式，供下游 Skill 直接消费。

---

## Skill 调用方式

当用户说 **"用 Skill XX"** 或 **"进入 [Skill名] 模式"** 时：
读取对应文件，严格按其角色准则、Workflow、输出格式执行，不得混用其他 Skill 的规范。

---

## Skill 索引

| 编号 | 名称 | 触发词 | 文件 |
|---|---|---|---|
| 01 | 市场洞察 | "市场调研"、"验证想法"、"I2M" | @.claude/skills/01-i2m.md |
| 02 | 产品需求 | "写PRD"、"产品设计"、"PRD" | @.claude/skills/02-prd.md |
| 03 | 系统架构 | "架构设计"、"技术选型"、"Arch" | @.claude/skills/03-arch.md |
| 04 | 开发编排 | "任务拆解"、"开发计划"、"Dev" | @.claude/skills/04-dev.md |
| 05 | 测试资产 | "写测试"、"QA"、"测试用例" | @.claude/skills/05-qa.md |
| 06 | 部署SRE | "部署方案"、"CI/CD"、"上线" | @.claude/skills/06-deploy.md |
| 07 | 增长运营 | "增长策略"、"埋点"、"Growth" | @.claude/skills/07-growth.md |
| 08 | 迭代演进 | "版本迭代"、"需求回顾"、"V2规划" | @.claude/skills/08-iteration.md |
| 09 | 安全合规 | "安全审查"、"合规检查"、"SecGuard" | @.claude/skills/09-security.md |

---

## 标准调用链

```
Skill 01 (市场洞察)
    └→ Skill 02 (产品需求) ←→ Skill 07 (增长钩子介入)
         └→ Skill 09 (安全合规审查)
              └→ Skill 03 (系统架构)
                   └→ Skill 04 (开发编排)
                        ├→ Skill 05 (测试资产生成)
                        └→ Skill 06 (部署SRE)
                             └→ Skill 07 (增长运营)
                                  └→ Skill 08 (迭代演进)
                                       └→ 回到 Skill 02 (下一轮迭代)
```

---

## 上下文压缩规则

在以下节点，当前 Skill 输出前必须附加"摘要（≤500字）"，供下游优先读取：
- Skill 02 输出后（PRD 摘要）
- Skill 03 输出后（架构决策摘要）
