# Auto-Exec Mechanism

> 自主执行编排机制 — 将开发目标自动分解为可执行任务，跨会话链式执行数小时，无需用户监督。

## 核心架构

```
主会话
  │
  ├── Phase 0-2: 意图分类 → 风险分级 → 任务分解
  │
  ├── Phase 3-4: 执行调度 (多子 Agent 并行)
  │     ├── A — 数据层 (trendscope / content-aggregator)
  │     ├── B — 语义层 (splitter / prompt-engine)
  │     ├── C — 交付层 (Story2Video / Multi-Publish)
  │     └── general — 文档/配置/测试
  │
  ├── Phase 4.6: Review Agent — 代码审查
  ├── Phase 4.7: E2E 自动验收
  └── Phase 5: 自适应记忆 → 清理
```

## 集成能力

| 机制 | 说明 |
|------|------|
| Intent Gate | 用户请求分类，决定是否触发 auto-exec |
| ECC 安全分级 | low/medium/high 三级风险，high 阻塞等待确认 |
| TDD 雪球 | bug fix 先写回归测试，RED→GREEN→REFACTOR |
| Review Checklist | 正确性/安全/架构/测试/PRD 七维审查 |
| PRD 门禁 | 功能变更必须同步 PRD |
| .plan/ 持久化 | 跨会话状态目录，scheduled task 轮询执行 |
| 多子 Agent 并行 | 按 ROLE_CARD 角色分组，无依赖任务并行 |
| Review Agent | 独立审查子 Agent，❌ 不通过不合并 |
| E2E 验收 | 全测试套件 + 集成验收 + 边界回归 |
| 资源感知调度 | 同资源任务串行（db/port/file/llm） |
| 自适应记忆 | 执行分析自动写入 memory/feedback |

## 文件结构

```
auto-exec-mechanism/
├── README.md              # 本文
├── SKILL.md               # auto-exec skill（可导入其他项目）
├── .plan/
│   └── README.md          # .plan/ 协议规范
├── dashboard/
│   └── auto-exec-dashboard.html  # 执行仪表盘
└── ROLE_CARD_MAPPING.md   # 角色映射参考
```

## 使用方式

### 方式 1: 自动触发

所有会话通过 `core-rules.md` 的 Intent Gate 自动评估 → 复杂任务自动走 auto-exec。

### 方式 2: 手动启动

```bash
# 在任何会话中说:
/auto-exec "<目标描述>"
```

### 方式 3: 跨会话执行

Auto-Exec 自动创建 scheduled task，每 2-5 分钟轮询一次 `.plan/` 状态目录，直到所有任务完成。

## 前置依赖

- Claude Desktop App with Cowork MCP
- `.plan/` 目录在 workspace 根目录
- GitHub PAT for PR 操作
- ROLE_CARD 文件在 `agent-patch/.cowork/`（可自定义）
