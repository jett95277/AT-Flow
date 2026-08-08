# 开发 AT Runtime（v2）

AT v2 是**个人辅助开发工具流中的记忆层**：管理三层记忆（short / medium /
long）的可见性、人工操作与生命周期；workflow / knowledge / execution 复用
开源技术。本文档是 v2 开发时必须遵守的工程原则与验证门。

## 核心判断

AT v2 的价值不是编排 agent，而是回答一个问题：

> 让人（和 Agent）清楚地看到当前记住了什么，并能在需要时查看、写入、提升、回滚。

因此优先级为：

1. 记忆可见：记忆是给人看的，Markdown 实时落盘，目录即视图
2. 记忆有 Scope：任何记忆都有归属（session/task/feature/project/role）
3. 记忆流动靠人：promotion / 清理是人工决策，不做自动 GC 与自动提炼
4. 生命周期可回滚：生命线节点全量快照，回滚前自动打恢复点
5. 其他全部复用：workflow / knowledge / execution 一律复用开源，不自研
6. **AT 不编排**：写入与打点由外部（Codex / Superpowers / 人工）触发

## 模块职责边界

### 核心（自研交付）

- `memory.py`：三层存储（Markdown 落盘 + YAML 多文档流元数据）、Memory URI、
  状态机操作（promote / archive / discard）、结构化写入（三字段）
- `view.py`：树视图渲染（short 折叠、medium/long 全显）
- `timeline.py`：生命线（checkpoint 全量快照 / timeline 列表 / rollback 恢复）
- `observer.py`：记忆操作审计事件（JSONL + 时间戳）
- `cli.py`：`at memory` 命令族

### V0.1 验证件（保留代码，移出核心，不再扩展）

`registry.py`、`context.py`、`policy.py`、`handoff.py`、`runner.py`、
`eval.py`、`execution.py`、`workspace.py`——v2.0 验证隔离与编排机制的产物。

## 存储布局

```text
.agent/
  manifest.yaml / policies.yaml
  runtime/  sessions/ tasks/ events/events.jsonl
  contexts/ bundles/
  memory/   short/ medium/ long/   （<scope>-<name>.md，追加式）
  timeline/ <ts>-<label>/          （meta.yaml + 三层全量快照）
  handoffs/ <id>.yaml
  artifacts/
  knowledge/refs/ <topic>.yaml
```

## 验证门（v2.1 每个 Task 必须满足）

1. 单元测试：`python -m unittest discover -s tests` 全绿
2. `at doctor` 通过
3. 机制只有在验证门中被使用才实现；未被使用的机制不实现
4. `at memory write` 三字段正确落盘（部分缺失允许、全缺失拒绝）
5. `at memory get` 结构化读取与写入一致（Agent 读取入口可用）
6. `at memory view` 树视图正确展示（short 折叠、medium/long 全显）
7. promote / archive / discard 状态流转正确；跨层 promote 同时迁移 scope
8. checkpoint 生成全量快照；timeline 列出节点；rollback 恢复并先打恢复点
9. 写 / 操作 / 打点 / 回滚均记录审计事件
10. checkpoint skill 触发词可触发打点

## 已知限制（诚实声明）

- 记忆质量依赖写入方（agent / 人工），噪音控制靠 AGENTS.md 约定与审计事件
- V0.1 验证件（隔离/编排）移出核心，不承诺为 AT 能力
- token 估算为 `len(text) // 4`（验证件遗留），不引入 tokenizer
- 不做自动 GC、自动提升、自动摘要、Web 面板
- 无 DB / Web / 网络依赖

## Git 约束（开发阶段）

- 开发中每个任务本地 commit（不 push），全部完成后统一 push
- commit message 使用英文 Conventional Commits
