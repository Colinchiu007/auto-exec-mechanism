# .plan/ — 自主执行状态目录

由 `auto-exec` 机制管理。跨会话持久化执行状态。

## 文件结构

```
.plan/
├── README.md         # 本文 — 协议说明
├── STATE.md          # 结构化状态（YAML 前注 + Markdown，真理源）
├── task_plan.md      # 任务清单 + 依赖 DAG + 状态
├── progress.md       # （已弃用，由 STATE.md 替代）
├── context/          # 额外参考上下文（可选）
└── notepads/         # Wisdom Accumulation 笔记
```

**STATE.md 是状态真理源**，替代原有的 `progress.md`。`progress.md` 不再手动编辑。

## task_plan.md 模板

```markdown
# 项目: <项目名>
# 目标: <一句话目标>
# 创建: <日期>

## 任务清单

| # | 任务 | 角色 | 依赖 | 风险 | 资源 | PRD | 测试 | 状态 |
|---|------|------|------|------|------|-----|------|------|
| 1 | 任务描述 | A | - | low | - | no | yes | pending |

## 说明
- DAG 图示
- 特殊注意事项
```

## STATE.md 格式

YAML 前注 + Markdown 正文。使用 `planning_cli.py` 读写，不要手动编辑。

### YAML 前注字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | int | 是 | 格式版本，当前为 1 |
| `goal` | string | 是 | 执行目标 |
| `scope` | string | 否 | 作用域（项目名） |
| `status` | enum | 是 | `planning` / `executing` / `phase_review` / `completed` / `blocked` |
| `created` | ISO 8601 | 是 | 创建时间 |
| `updated` | ISO 8601 | 是 | 最后更新时间 |
| `metrics.total_plans` | int | 否 | 计划总数 |
| `metrics.completed_plans` | int | 否 | 已完成 |
| `metrics.failed_plans` | int | 否 | 失败 |
| `metrics.blocked_plans` | int | 否 | 阻塞 |
| `metrics.phase` | int | 否 | 当前阶段编号 |
| `metrics.started_at` | ISO 8601 | 否 | 开始时间 |
| `metrics.completed_at` | ISO 8601 | 否 | 完成时间 |
| `decisions` | list | 否 | 决策记录 |
| `blockers` | list | 否 | 阻塞项 |
| `current_plan` | int | 否 | 当前执行中的计划编号 |

### decisions 条目

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | int | 是 | 自增编号 |
| `summary` | string | 是 | 决策摘要 |
| `rationale` | string | 否 | 决策原因 |
| `timestamp` | ISO 8601 | 是 | 记录时间 |

### blockers 条目

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | int | 是 | 自增编号 |
| `text` | string | 是 | 阻塞描述 |
| `status` | enum | 是 | `open` / `resolved` |
| `created` | ISO 8601 | 是 | 创建时间 |
| `resolved` | ISO 8601 | 否 | 解决时间 |

### 示例

```yaml
---
version: 1
goal: "实现 auth 模块重构"
scope: "shared-models, platform-orchestrator"
status: executing
created: "2026-06-27T10:00:00"
updated: "2026-06-27T11:30:00"
metrics:
  total_plans: 4
  completed_plans: 2
  failed_plans: 0
  blocked_plans: 1
  phase: 2
  started_at: "2026-06-27T10:05:00"
  completed_at: null
decisions:
  - id: 1
    summary: "JWT 令牌改用 HS256 + 共享密钥"
    rationale: "单服务架构不需要 RS256 的开销"
    timestamp: "2026-06-27T10:00:00"
blockers:
  - id: 1
    text: "需要确认 PO_SECRET_KEY 轮换策略"
    status: open
    created: "2026-06-27T10:30:00"
    resolved: null
current_plan: 3
---
```

### 正文约定

YAML 前注下方可包含 Markdown 格式的执行日志，用于人读。机器读状态时只解析前注。

## 生命周期

1. 主会话规划 → 写入 `task_plan.md` + `STATE.md`
2. Scheduled task 每次触发：读 STATE.md → 执行 → `planning_cli.py state update` 写回
3. 全部完成 + E2E 验收通过 → 清理 `.plan/` → 禁用 scheduled task

## 工具

参见 `tools/README.md` 中的 `planning_cli.py`（状态管理 CLI）和 `nyquist_check.py`（上下文窗口校验）。
