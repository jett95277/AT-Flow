# 开发 AT Runtime（v2）

v2.0 将 AT 从“多 Agent 编排平台”重构为 **Context & Memory Control Plane**。
本文档记录 v2 开发时必须遵守的工程原则与验证门，是后续实现、重构和评审的
判断标准。

## 核心判断

AT v2 的价值不是控制台外观，也不是把多个 agent 串起来，而是回答一个问题：

> 当前 Agent 在当前任务阶段，应该看到什么，不应该看到什么。

因此优先级为：

1. Context 是构造出来的（每次动态构建，不继承会话）
2. Memory 必须带 Scope（short/medium/long + 作用域）
3. Agent 之间只通过 Handoff/Artifact 交换，不复制完整对话
4. 权限由静态 Policy 决定，relevance 由显式引用 + 默认最小集决定
5. 可恢复、可观测、可测试的进程级隔离 runtime

## 模块职责边界

- `workspace.py`：`.agent/` 初始化、manifest/policies 读写
- `registry.py`：Task / Session 的创建与状态，不保存 LLM 思维过程
- `context.py`：Context Router + Assembler，产出 Context Bundle
- `memory.py`：三层记忆 + URI 解析 + 追加式 Markdown 存储
- `policy.py`：静态 read/write 权限判定
- `handoff.py`：结构化 Handoff 落盘（YAML）
- `knowledge.py`：本地 `wiki://` 引用层（query/get/propose）
- `observer.py`：机器可读事件（JSONL）
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
  handoffs/ <id>.yaml
  artifacts/
  knowledge/refs/ <topic>.yaml
```

## 验证门（每个 Task 必须满足）

1. 单元测试：`python -m unittest discover -s tests` 全绿
2. `at doctor` 通过
3. 机制只有在验证门中被使用才实现；未被使用的机制不实现
4. 真实 Codex 冒烟（可选但有改动时必须说明是否执行）

## 已知限制（V0.1 明确接受）

- relevance 只靠显式引用 + 静态规则 + 默认最小集，不做 LLM 检索
- token 估算为 `len(text) // 4`，不引入 tokenizer
- Memory Promotion 手动触发（`at memory promote` 预留），无自动提炼与 GC
- 无 Web / DB / 网络依赖；Execution 是逐 session 进程调用
