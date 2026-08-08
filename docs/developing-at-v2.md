# 开发 AT Runtime（v2）

AT v2 是**个人辅助开发工具流中的记忆层**：管理三层记忆（short / medium /
long）的可见性、人工操作与生命周期；workflow / knowledge / execution 复用
开源技术。本文档是 v2 开发时必须遵守的工程原则与验证门。

## 核心判断

AT v2 的价值不是控制台外观，也不是把多个 agent 串起来，而是回答一个问题：

> 让人（和 Agent）清楚地看到当前记住了什么，并能在需要时查看、提升、回滚。

因此优先级为：

1. 记忆可见：记忆是给人看的，Markdown 实时落盘，目录即视图
2. 记忆有 Scope：任何记忆都有归属（session/task/feature/project/role）
3. 记忆流动靠人：promotion / 清理是人工决策，不做自动 GC 与自动提炼
4. 生命周期可回滚：生命线节点全量快照，随时查看、可回滚（回滚前自动打
   恢复点）
5. 其他全部复用：workflow / knowledge / execution 一律复用开源，不自研

## 模块职责边界

### 核心（自研交付）

- `memory.py`：三层存储（Markdown 落盘 + YAML 多文档流元数据）、Memory URI、
  状态机操作（promote / archive / discard）
- `view.py`：树视图渲染（三层全貌、scope 分组、状态/来源/时间）
- `timeline.py`：生命线（checkpoint 全量快照 / timeline 列表 / rollback 恢复）
- `observer.py`：记忆读写与操作审计事件（JSONL + 时间戳）
- `cli.py`：`at memory` 命令族

### 支撑（最小脚手架，不扩展）

- `workspace.py`：`.agent/` 初始化、manifest/policies 读写
- `registry.py`：Task / Session 创建与状态
- `context.py`：Context Router + Assembler，产出 Context Bundle
- `policy.py`：静态 read/write 权限判定（读侧过滤已接线）
- `handoff.py`：结构化 Handoff 落盘（YAML）
- `knowledge.py`：本地 `wiki://` 引用层（query/get/propose）
- `execution.py`：ExecutionAdapter / LocalAdapter（进程级隔离）
- `runner.py`：三 session 流程编排 + doctor
- `eval.py`：baseline 单会话 vs AT 三会话的最小对比

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
4. memory 写读往返保真（多行 content、嵌套 source）
5. promote / archive / discard 状态流转正确且落盘
6. checkpoint 生成全量快照；timeline 列出节点；rollback 恢复并先打恢复点
7. checkpoint skill 触发词可触发打点

## 已知限制（诚实声明）

- 隔离是 API/命名空间级（软隔离）：读侧 Policy 过滤已强制，写侧 `can_write`
  未接线；执行 sandbox 限制（`.agent/` 只读/不可见）是信任模型决策点
- relevance 只靠显式引用 + 静态规则 + 默认最小集，不做 LLM 检索
- token 估算为 `len(text) // 4`，不引入 tokenizer
- 不做自动 GC、自动提升、自动摘要、Web 面板
- 无 DB / Web / 网络依赖；Execution 是逐 session 进程调用

## Git 约束（开发阶段）

- 开发中每个任务本地 commit（不 push），全部完成后统一 push
- commit message 使用英文 Conventional Commits
