---
name: auto-exec
description: 自主执行编排 — 将开发目标自动分解为可执行任务，通过多子 Agent 并行 + Review Agent + E2E 验收 + 资源调度 + 自适应记忆，跨会话链式执行
---

# Auto-Exec 自主执行编排

参见 [README.md](README.md) 获取完整架构说明。

## 快速集成

将本 `SKILL.md` 导入你的 Claude 技能系统，即可在任何会话中使用 `/auto-exec`。

### 导入步骤

1. 将本目录放入你的 `.claude/skills/` 或通过 Cowork skill manager 导入
2. 在 `core-rules.md` 的 Intent Gate 后添加 auto-exec 触发规则
3. 创建 `.plan/` 目录（参照 `.plan/README.md`）
4. 自定义 `ROLE_CARD_MAPPING.md` 中的角色映射

### 核心配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| ROLE_CARD 路径 | `agent-patch/.cowork/` | 各角色身份卡 |
| .plan/ 路径 | 项目根目录 | 跨会话状态目录 |
| 轮询间隔 | */5 * * * * | 每 5 分钟 |
| Review Agent | 按 risk 触发 | high/medium+code/shared-models 必须 |

### 自定义角色

编辑 `ROLE_CARD_MAPPING.md` 中的角色映射表，适配你的项目结构：
