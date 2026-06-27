# .plan/ — 自主执行状态目录

由 `auto-exec` 机制管理。跨会话持久化执行状态。

## 文件结构

```
.plan/
├── README.md         # 本文 — 协议说明
├── task_plan.md      # 任务清单 + 依赖 DAG + 状态
├── progress.md       # 执行进度 + 决策记录
└── context/          # 额外参考上下文（可选）
```

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

## progress.md 模板

```markdown
# 进度

## 当前状态
- 当前任务: #
- 已完成: #/#
- 本轮执行: <时间戳>
- 已派发子 Agent: [A, B, ...]

## 决策记录
- <决策内容> — <决策原因>

## Review 记录
- #1 Review Agent ⚠️: 建议加日志
- #3 Review Agent ❌: 未 PRD 同步 — 已退回

## 阻塞项（需你确认）
- [ ] 高风险操作 #N: <描述>
```

## 列说明

| 列 | 必填 | 说明 |
|----|------|------|
| # | 是 | 编号 |
| 任务 | 是 | 描述 |
| 角色 | 是 | A/B/C/general — 决定子 Agent 类型 |
| 依赖 | 否 | 前置任务编号 |
| 风险 | 是 | low/medium/high |
| 资源 | 否 | db / port:N / file:xxx / llm — 同资源串行 |
| PRD | 是 | 是否需要同步 PRD |
| 测试 | 是 | 是否需要测试 |
| 状态 | 是 | pending/in_progress/completed/failed/blocked |

## 生命周期

1. 主会话规划 → 写入 `task_plan.md` + `progress.md`
2. Scheduled task 每次触发：读 progress → 执行 → 写 progress
3. 全部完成 + E2E 验收通过 → 清理 `.plan/` → 禁用 scheduled task
