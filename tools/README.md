# Tools — 开发辅助工具集

> oh-my-openagent 启发的 6 个独立 CLI 工具，覆盖编辑、规划、路由、协作等场景。

## 工具清单

| 工具 | 优先级 | 功能 | 运行方式 |
|------|--------|------|---------|
| `hash_anchor.py` | P0-1 | Hash-Anchored Editing — 行级哈希校验编辑，防止过期行编辑 | `python hash_anchor.py <command> <file>` |
| `init_deep.py` | P0-2 | 层级化 AGENTS.md 自动生成（project → src → subdir） | `python init_deep.py [project]` |
| `planning_pipeline.py` | P1-1 | Prometheus → Metis → Momus 三阶段规划管线 | `python planning_pipeline.py --goal "..."` |
| `planning_cli.py` | P0-1 | STATE.md 状态管理 CLI — get/update/patch/add-decision/add-blocker | `python planning_cli.py state get` |
| `nyquist_check.py` | P0-1 | 上下文窗口校验 — plan token 估算 + budget 检查 | `python nyquist_check.py check <file>` |
| `notepads.py` | P1-2 | Wisdom Accumulation — 结构化 .plan/notepads/ 系统 | `python notepads.py <command>` |
| `model_routing.py` | P2 | 多模型路由 — 5 分类关键词评分路由 | `python model_routing.py classify "..."` |
| `team_mode.py` | P3 | 多 Agent 并行协作框架（4 角色 + ASCII dashboard） | `python team_mode.py init <goal>` |

## 路径配置

部分工具硬编码了 `PROJECTS_ROOT`。可通过环境变量覆盖：

```bash
# 设置工作区根目录（默认当前会话路径）
export PROJECTS_ROOT=/path/to/projects

# model_routing.py 的配置文件路径
export MODEL_ROUTES_PATH=/path/to/model_routes.json

# planning_pipeline.py 的知识图谱路径
export GRAPH_PATH=/path/to/graph.json
```

## 依赖

所有工具均为纯 Python 3.12+ 标准库，无需额外安装依赖。
