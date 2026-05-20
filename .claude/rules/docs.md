# 文档组织规范

## 目录结构

```
docs/
├── product/          # 产品文档（长期维护，跨版本）
│   └── PRD.md        # 产品需求文档
├── architecture/     # 架构文档（长期维护，跨版本）
│   └── Architecture.md
├── engineering/      # 工程规范与编排
│   └── DevOrchestration.md
├── qa/               # 测试
│   ├── TestPlan.md
│   └── TestReport.md
├── guides/           # 用户/部署指南
├── plans/            # 活跃方案（进行中或待执行）
│   ├── feature/      #   功能设计
│   └── refactor/     #   重构方案
├── archive/          # 已完成方案（只读归档）
└── assets/           # 二进制资源
```

## 新建文档规则

| 规则 | 说明 |
|------|------|
| **命名风格** | 全部 kebab-case（`audio-pipeline-design.md`），禁止 snake_case 或中文文件名 |
| **分类放置** | 活跃方案放 `plans/`，完成后移入 `archive/`；二进制放 `assets/` |
| **根目录禁放** | `docs/` 根目录仅放 `README.md` 导航索引，禁止新增其他文件 |
| **归档判定** | 方案实施完成且验证通过后，移入 `archive/` 对应子目录 |
| **导航同步** | 新增或移动文件后，必须同步更新 `docs/README.md` 索引 |

## 文档路径约定

| 文档 | 正确路径 |
|------|---------|
| PRD | `docs/product/PRD.md` |
| Architecture | `docs/architecture/Architecture.md` |
| DevOrchestration | `docs/engineering/DevOrchestration.md` |
| TestPlan | `docs/qa/TestPlan.md` |
| TestReport | `docs/qa/TestReport.md` |
