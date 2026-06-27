# 角色映射参考

## 默认映射

| 角色 | 管辖项目 | 说明 |
|------|---------|------|
| A — 数据层 | trendscope, content-aggregator, content-aggregator-shared | 爬虫/采集/改写 |
| B — 语义层 | smart-sentence-splitter, prompt-engine, shared-models | 分句/提示词优化 |
| C — 交付层 | Story2Video, Multi-Publish, platform-orchestrator | 视频合成/发布/编排 |
| general | 文档/配置/测试/跨项目 | 通用任务 |

## 自定义指南

编辑 `agent-patch/.cowork/ROLE_CARD_{ROLE}.md` 或在你的项目中创建对应角色文件。

### ROLE_CARD 模板

```markdown
# 🅰️ Agent {角色名} — {层名}

**一句话**: {职责描述}

## 管辖项目

| 项目 | 路径 | 职责 |
|------|------|------|
| {项目名} | {路径} | {职责} |

## 上下游

上游: {上游依赖}
下游: {下游消费者}

## 开发环境

```bash
# 测试命令
pytest tests/ -v
# 启动命令
uvicorn main:app --reload --port 8000
```

## 工作规范

**必须做:**
- {规则1}
- {规则2}

**不能做:**
- {禁止事项1}
- {禁止事项2}
```
