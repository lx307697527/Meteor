# VoiceIME Wiki Index

> 需求业务/设计上下文时，先读本文件路由到对应 digest，再按需读源文档补细节。
> 代码级查询（函数定位、调用关系、影响分析）用 CodeGraph MCP，不走 wiki。
> 编码防坑查 `.claude/agent.md`。

## Digests

| Digest | 行数 | 查阅场景 | 源文档 |
|--------|------|---------|--------|
| [prd-digest.md](prd-digest.md) | ~150 | 功能规格、交互流程、性能指标、优先级 | docs/product/PRD.md |
| [arch-digest.md](arch-digest.md) | ~100 | 技术选型、数据模型、模块分层 | docs/architecture/Architecture.md |

## Quick Routing

- "功能 P0/P1/P2 分别有哪些？" / "悬浮条交互？" → prd-digest.md
- "技术栈？" / "数据怎么存？" / "模块间怎么调用？" → arch-digest.md
- "编码注意事项？" / "已知坑位？" → .claude/agent.md
- "函数 X 在哪定义？" → CodeGraph MCP

## Version Tracking

| Digest | Source Version | Last Synced |
|--------|---------------|-------------|
| prd-digest.md | PRD V1.0 | 2026-05-21 |
| arch-digest.md | Architecture (pending) | — |
