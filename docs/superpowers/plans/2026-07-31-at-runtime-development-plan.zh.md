# AT 终极 Runtime 开发实施计划

> **给 agentic workers：**实现本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按任务逐项推进。步骤使用 checkbox（`- [ ]`）跟踪。

**目标：**把 AT Flow 建成最终形态的多 agent 协作 runtime：保留 AT 现有的 agent 隔离、状态机、context contract、memory proposal、trace/audit，同时吸收白泽系统的专题记忆、时间线连续性、SOP 路由、persona overlay、启动交互和一次性审批机制。

**架构：**AT 继续保持 Python 标准库 runtime。runtime 负责状态流转、专题注册表、时间线、session 归档、SOP 路由、persona 选择、上下文构建、handoff 路由、记忆 proposal 审核、审计、审批、重试、provider 检查和 ASCII 展示。provider 只执行单个受限 agent step，并且只能使用 `context.json` 中显式列出的路径。

**技术栈：**Python 标准库、`unittest`、JSON contract、Markdown memory 文件、PowerShell 友好的 CLI、ASCII chat rendering。

## 唯一实施计划

这份文件是 AT Flow 吸收白泽系统设计后的**中文终极实施计划**。

英文对应文件：

- `docs/superpowers/plans/2026-07-31-at-runtime-development-plan.md`

上层设计依据：

- `docs/superpowers/specs/2026-07-31-baize-at-integration-design.md`

支撑原则文档：

- `docs/developing-at.md`
- `docs/runtime-contracts.md`
- `docs/architecture.md`

## 全局约束

- 除非后续计划明确批准，否则保持零外部依赖。
- 所有行为变更必须走 TDD：先写失败测试，运行确认失败，再写最小实现，再运行确认通过。
- 基线验证命令是 `python -m unittest discover -s tests`。
- 声称代码完成前必须运行 `python -m compileall src tests at.py`。
- 默认 agent pipeline 顺序保持 `main -> analysis -> code -> test`。
- 默认 process provider 环境不能暴露 `AT_WORKSPACE_ROOT`、`AT_SHARED_ROOT`、`AT_SESSION_DIR`。
- agent 不能直接写 `.at/shared/memory`、`.at/shared/skills`、`.at/shared/policies`、其他 agent 目录、`state.json` 或 `handoff`。
- persona 和 SOP 不能覆盖 `permissions.json`。
- 不直接导入已经损坏编码的白泽 markdown 文件。
- 不依赖白泽的 SQLite 数据库。
- 不把 Bash 作为必需 runtime 依赖。
- 不增加自动 commit 或自动 push。
- ASCII/TUI 只是展示层；runtime contract、恢复、artifact、audit、approval、测试优先级更高。
- 当前 workspace 没有 `.git` 目录，所以每个任务以验证检查点结束，不以 git commit 结束。

---

## 开发节点

1. 状态生命周期与恢复
2. 专题 runtime
3. 时间线与 session 归档
4. Context selection contract v2
5. SOP 路由
6. Persona overlay
7. Memory proposal 审核与应用
8. Artifact 校验与 handoff 契约
9. 可观测性命令
10. Retry / abort / reroute 控制
11. Approval guard
12. Provider capability 检查
13. 端到端场景测试
14. 对话框 ASCII polish

---

### 任务 1：状态生命周期与恢复

**文件：**
- 修改：`src/at_flow/models.py`
- 修改：`src/at_flow/transitions.py`
- 修改：`src/at_flow/engine.py`
- 测试：`tests/test_runtime_contracts.py`
- 文档：`docs/runtime-contracts.md`

**接口：**
- 消费：`SessionState`、`StepState`、`transition_step()`、`retry_failed_step()`
- 产出：`recover_interrupted_step(session: SessionState, step_index: int, reason: str) -> None`
- 产出：`SessionState.interrupted_steps() -> list[int]`

- [ ] **步骤 1：写失败测试**

在 `tests/test_runtime_contracts.py` 中新增测试：构造一个只有 `main` 的 session，把 step 转成 `running`，调用 `recover_interrupted_step()` 后断言：

- step 变成 `failed`
- `failure_reason` 包含恢复原因
- `retryable` 为 `True`
- session 状态为 `failed`

- [ ] **步骤 2：运行定向测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_runtime_contracts.RuntimeContractsTests.test_running_step_can_be_marked_failed_during_recovery
```

预期失败：

```text
NameError: name 'recover_interrupted_step' is not defined
```

- [ ] **步骤 3：实现恢复 helper**

在 `SessionState` 增加 `interrupted_steps()`，返回所有 `running` step 的 index。

在 `transitions.py` 增加 `recover_interrupted_step()`：只允许恢复 `running` step；非 `running` 状态抛 `TransitionError`；恢复后通过 `transition_step(..., "failed", retryable=True)` 标记失败。

- [ ] **步骤 4：接入 `Runner.run()`**

加载 session 后，如果发现 interrupted step，则恢复第一个 running step，记录 `recover_interrupted_step` trace，保存 session，并停止 run loop，让用户显式选择 retry。

- [ ] **步骤 5：验证任务 1**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_runtime_contracts
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 2：专题 Runtime

**文件：**
- 新增：`src/at_flow/topics.py`
- 修改：`src/at_flow/workspace.py`
- 修改：`src/at_flow/cli.py`
- 测试：`tests/test_topics.py`
- 文档：`docs/runtime-contracts.md`
- 文档：`README.md`

**接口：**
- 产出：`TopicRecord`
- 产出：`TopicIndex`
- 产出：`load_topic_index(workspace: ATWorkspace) -> TopicIndex`
- 产出：`create_topic(workspace: ATWorkspace, name: str) -> TopicRecord`
- 产出：`switch_topic(workspace: ATWorkspace, query: str) -> TopicRecord`
- 产出：`active_topic(workspace: ATWorkspace) -> TopicRecord | None`
- 产出：CLI 命令 `topic list`、`topic create`、`topic switch`、`topic status`

- [ ] **步骤 1：写失败测试**

创建 `tests/test_topics.py`，覆盖：

- `create_topic("AT Runtime")` 会创建 topic record
- 自动设置 active topic
- 创建 `.at/topics/<topic-id>/topic.json`
- 创建 `context.md`
- 创建 `context_summary.md`
- 创建 `timeline.md`
- 创建 `sessions/`
- 创建 `artifacts/`
- 创建 `references/`
- `switch_topic("Baize")` 能按名称片段切换 active topic

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_topics
```

预期失败：

```text
ModuleNotFoundError: No module named 'at_flow.topics'
```

- [ ] **步骤 3：实现 workspace topic 路径**

在 `ATWorkspace` 增加：

- `topics_root`
- `topic_index_path()`

`ensure_layout()` 必须创建 `.at/topics/`。

- [ ] **步骤 4：实现 `topics.py`**

实现：

- `TopicRecord`
- `TopicIndex`
- 读取/保存 `.at/topics/index.json`
- 从 topic name 生成稳定 slug
- 创建 topic 目录和默认文件
- 更新 active topic
- 处理按 id 或名称片段切换 topic

- [ ] **步骤 5：增加 CLI topic 命令**

新增：

```text
topic list
topic create <name>
topic switch <id-or-name>
topic status
```

输出必须是纯文本，并适合 Codex 对话框展示。

- [ ] **步骤 6：验证任务 2**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_topics
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 3：时间线与 Session 归档

**文件：**
- 新增：`src/at_flow/timeline.py`
- 修改：`src/at_flow/topics.py`
- 修改：`src/at_flow/cli.py`
- 修改：`src/at_flow/render.py`
- 测试：`tests/test_timeline.py`
- 文档：`docs/runtime-contracts.md`
- 文档：`README.md`

**接口：**
- 产出：`append_timeline_event(workspace: ATWorkspace, topic_id: str, kind: str, ref: str, message: str) -> Path`
- 产出：`read_timeline(workspace: ATWorkspace, topic_id: str, limit: int = 5) -> list[str]`
- 产出：`save_session_archive(workspace: ATWorkspace, session_id: str, topic_id: str | None = None) -> Path`
- 产出：CLI 命令 `topic timeline`、`save-session`

- [ ] **步骤 1：写失败测试**

创建 `tests/test_timeline.py`，覆盖：

- 给 topic 追加一条 `decision` timeline event
- 读取 timeline 能看到 kind 和 message
- 保存 session archive 会写入 `.at/topics/<topic-id>/sessions/<session-id>.md`
- archive 内容包含原 session task

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_timeline
```

预期失败：

```text
ModuleNotFoundError: No module named 'at_flow.timeline'
```

- [ ] **步骤 3：实现 timeline 追加/读取**

`timeline.md` 每行格式：

```text
YYYY-MM-DD HH:MM | <kind> | <ref> | <message>
```

支持读取最近 N 条，默认 5 条。

- [ ] **步骤 4：实现 session archive**

archive 路径：

```text
.at/topics/<topic-id>/sessions/<session-id>.md
```

archive 至少包含：

- session id
- topic id
- task
- status
- provider
- steps
- artifacts
- failures
- next suggested action

- [ ] **步骤 5：增加 CLI 和启动面板数据**

新增：

```text
topic timeline <id-or-name>
save-session <session-id>
```

`panel --format chat` 在 AT 状态机之后展示 active topic 和 recent timeline。

- [ ] **步骤 6：验证任务 3**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_timeline
$env:PYTHONPATH='src'; python -m unittest tests.test_render
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 4：Context Selection Contract V2

**文件：**
- 修改：`src/at_flow/context_contracts.py`
- 修改：`src/at_flow/providers.py`
- 修改：`src/at_flow/topics.py`
- 测试：`tests/test_context_memory_contracts.py`
- 测试：`tests/test_topics.py`
- 文档：`docs/runtime-contracts.md`

**接口：**
- 消费：`build_agent_context_contract(context: AgentContext) -> dict[str, Any]`
- 产出：`list_authorized_shared_files(shared_root: Path, permissions: dict[str, Any]) -> dict[str, list[str]]`
- 产出：context JSON 字段 `selected_files`、`topic`、`sop`、`persona`

- [ ] **步骤 1：写失败测试**

在 `tests/test_context_memory_contracts.py` 中新增测试：

- 创建 topic
- 创建 session
- 跑一个 mock main step
- 读取 `context/<agent>.json`
- 断言包含 `selected_files`
- 断言包含 `topic`
- 断言 topic id 匹配 active topic
- 断言不包含 `shared_root`
- 断言不包含 `session_dir`
- 断言不包含 `workspace_root`

- [ ] **步骤 2：运行定向测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_context_memory_contracts.ContextMemoryContractTests.test_context_contract_lists_selected_files_topic_and_no_roots
```

预期失败：

```text
AssertionError: 'selected_files' not found
```

- [ ] **步骤 3：实现授权文件选择**

`list_authorized_shared_files()` 按 `permissions.json` 的 read 权限选择：

- `shared_memory` -> `.at/shared/memory` 文件
- `shared_skills` -> `.at/shared/skills` 文件
- `shared_policies` -> `.at/shared/policies` 文件
- `shared_docs` -> `.at/shared/docs` 文件

返回具体文件路径，不返回 shared root。

- [ ] **步骤 4：加入 topic/persona/SOP 字段**

`context.json` 必须包含：

```json
{
  "topic": {"id": "...", "name": "...", "summary_path": "...", "timeline_path": "..."},
  "persona": null,
  "sop": null
}
```

没有选择时用 `null`。不能暴露完整 topic root。

- [ ] **步骤 5：验证任务 4**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_context_memory_contracts
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 5：SOP 路由

**文件：**
- 新增：`src/at_flow/sop.py`
- 修改：`src/at_flow/workspace.py`
- 修改：`src/at_flow/context_contracts.py`
- 修改：`src/at_flow/cli.py`
- 测试：`tests/test_sop.py`
- 文档：`docs/runtime-contracts.md`
- 文档：`README.md`

**接口：**
- 产出：`SOPRoute`
- 产出：`load_sop_routes(workspace: ATWorkspace) -> list[SOPRoute]`
- 产出：`match_sop(workspace: ATWorkspace, text: str) -> list[SOPRoute]`
- 产出：CLI 命令 `sop match <text>`

- [ ] **步骤 1：写失败测试**

创建 `tests/test_sop.py`，覆盖：

- workspace 初始化后存在 `.at/shared/sop/routing.json`
- 存在 `.at/shared/sop/save-session.md`
- `load_sop_routes()` 能读到 `save-session`
- `match_sop("保存当前会话")` 命中 `save-session`

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_sop
```

预期失败：

```text
ModuleNotFoundError: No module named 'at_flow.sop'
```

- [ ] **步骤 3：初始化 SOP 目录**

`ensure_layout()` 必须创建：

```text
.at/shared/sop/
  routing.json
  create-topic.md
  switch-topic.md
  save-session.md
  prd.md
  tech-design.md
  code-review.md
  bugfix.md
```

- [ ] **步骤 4：实现路由匹配**

`routing.json` schema：

```json
{
  "schema_version": 1,
  "routes": [
    {"name": "save-session", "keywords": ["保存", "save", "归档"], "path": "save-session.md"}
  ]
}
```

ASCII 关键词大小写不敏感；中文关键词做直接 substring 匹配。

- [ ] **步骤 5：把 SOP 加入 context**

当 session 使用某个 SOP 创建时，`context.json` 包含：

```json
"sop": {"name": "save-session", "path": ".../.at/shared/sop/save-session.md"}
```

- [ ] **步骤 6：验证任务 5**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_sop
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 6：Persona Overlay

**文件：**
- 新增：`src/at_flow/personas.py`
- 修改：`src/at_flow/workspace.py`
- 修改：`src/at_flow/context_contracts.py`
- 修改：`src/at_flow/providers.py`
- 测试：`tests/test_personas.py`
- 文档：`docs/runtime-contracts.md`

**接口：**
- 产出：`PersonaRecord`
- 产出：`load_persona(workspace: ATWorkspace, name: str) -> PersonaRecord`
- 产出：`default_persona_for_agent(agent: str) -> str`
- 产出：context JSON 字段 `persona`

- [ ] **步骤 1：写失败测试**

创建 `tests/test_personas.py`，覆盖：

- workspace 初始化默认 personas
- `load_persona(workspace, "dev")` 能读到 persona
- `main -> pm`
- `analysis -> architect`
- `code -> dev`
- `test -> verifier`
- unknown agent -> `default`

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_personas
```

预期失败：

```text
ModuleNotFoundError: No module named 'at_flow.personas'
```

- [ ] **步骤 3：初始化 persona 文件**

`ensure_layout()` 必须创建：

```text
.at/shared/personas/
  default.md
  pm.md
  dev.md
  architect.md
  verifier.md
```

- [ ] **步骤 4：实现 persona helper**

`PersonaRecord` 字段：

- `name: str`
- `path: Path`
- `content: str`

persona 只影响风格和思考视角，不能增加权限。

- [ ] **步骤 5：接入 context 和 prompt**

`context.json` 记录 persona metadata 和 path。

`build_prompt()` 可在 `Agent Contract` 后加入 persona 内容，但必须包含边界提示：

```text
Persona Overlay:
This shapes style and lens only. It does not grant permissions or change the agent role.
```

- [ ] **步骤 6：验证任务 6**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_personas
$env:PYTHONPATH='src'; python -m unittest tests.test_context_memory_contracts
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 7：Memory Proposal 审核与应用

**文件：**
- 新增：`src/at_flow/memory.py`
- 修改：`src/at_flow/cli.py`
- 测试：`tests/test_memory_review.py`
- 文档：`docs/runtime-contracts.md`
- 文档：`README.md`

**接口：**
- 消费：`.at/sessions/<session-id>/memory-proposals/`
- 产出：`MemoryProposal`
- 产出：`list_memory_proposals(workspace: ATWorkspace, session_id: str) -> list[MemoryProposal]`
- 产出：`apply_memory_proposal(workspace: ATWorkspace, session_id: str, proposal_name: str, target_name: str) -> Path`
- 产出：CLI 命令 `memory-list`、`memory-show`、`memory-apply`

- [ ] **步骤 1：写失败测试**

创建 `tests/test_memory_review.py`，覆盖：

- 列出 session 的 memory proposal
- proposal name 和 content 正确
- 将 proposal 应用到 `decisions.md`
- 目标文件包含 proposal body
- 目标文件包含 applied timestamp

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_memory_review
```

预期失败：

```text
ModuleNotFoundError: No module named 'at_flow.memory'
```

- [ ] **步骤 3：实现 memory helper**

创建 `src/at_flow/memory.py`，实现：

- `MemoryProposal`
- `list_memory_proposals()`
- `apply_memory_proposal()`

必须安全处理 proposal name：如果 `Path(name).name != name`，拒绝。

- [ ] **步骤 4：增加 CLI 命令**

新增：

```text
memory-list <session-id>
memory-show <session-id> <proposal-name>
memory-apply <session-id> <proposal-name> <target-name>
```

- [ ] **步骤 5：应用后写入 timeline**

如果存在 active topic，应用 proposal 后追加：

```text
<time> | memory | <proposal-name> | Applied to <target-name>
```

- [ ] **步骤 6：验证任务 7**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_memory_review
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 8：Artifact 校验与 Handoff 契约

**文件：**
- 新增：`src/at_flow/artifacts.py`
- 修改：`src/at_flow/engine.py`
- 测试：`tests/test_artifact_contracts.py`
- 文档：`docs/runtime-contracts.md`

**接口：**
- 消费：`outbox/artifact.md`、`output.md`
- 产出：`validate_artifact_contract(agent: str, output_contract: str, artifact: str) -> list[str]`
- 产出：trace event `artifact_contract_failed`

- [ ] **步骤 1：写失败测试**

创建 `tests/test_artifact_contracts.py`：

- `output.md` 要求 `Changed Files`、`Behavioral Changes`、`Verification Suggestions`
- artifact 只包含 `## Changed Files`
- 断言 missing sections 为 `["Behavioral Changes", "Verification Suggestions"]`

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_artifact_contracts
```

预期失败：

```text
ModuleNotFoundError: No module named 'at_flow.artifacts'
```

- [ ] **步骤 3：实现 artifact validator**

创建 `src/at_flow/artifacts.py`：

- 从 `output.md` 的 bullet 行解析必需 section
- 从 artifact markdown heading 解析已出现 section
- 返回缺失 section 列表

- [ ] **步骤 4：接入 runner**

`_collect_output()` 后校验 artifact。若缺 section：

- 写 `failure.json`
- step 标记为 failed
- `retryable=True`
- 不 route handoff
- trace 记录 `artifact_contract_failed`

- [ ] **步骤 5：验证任务 8**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_artifact_contracts
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 9：可观测性命令

**文件：**
- 新增：`src/at_flow/inspectors.py`
- 修改：`src/at_flow/cli.py`
- 修改：`src/at_flow/render.py`
- 测试：`tests/test_observability_cli.py`
- 文档：`README.md`

**接口：**
- 产出：`session_trace_summary(workspace: ATWorkspace, session_id: str) -> list[dict[str, Any]]`
- 产出：`session_audit_summary(workspace: ATWorkspace, session_id: str) -> list[dict[str, Any]]`
- 产出：CLI 命令 `trace`、`audit`、`artifact`、`doctor`

- [ ] **步骤 1：写失败测试**

创建 `tests/test_observability_cli.py`：

- 跑一个 mock `main` step
- 调用 `session_trace_summary()`
- 断言包含 `prepare_agent`
- 断言包含 `build_context`
- 断言包含 `collect_output`
- 断言包含 `audit_permissions`

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_observability_cli
```

预期失败：

```text
ModuleNotFoundError: No module named 'at_flow.inspectors'
```

- [ ] **步骤 3：实现 inspectors**

读取：

- `trace.jsonl`
- `audit/*.json`
- artifacts
- failures
- context paths
- topic status
- provider config availability

- [ ] **步骤 4：增加 CLI 命令**

新增：

```text
trace <session-id>
audit <session-id>
artifact <session-id> <agent>
doctor
```

- [ ] **步骤 5：验证任务 9**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_observability_cli
$env:PYTHONPATH='src'; python .\at.py doctor
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 10：Retry / Abort / Reroute 控制

**文件：**
- 修改：`src/at_flow/transitions.py`
- 修改：`src/at_flow/engine.py`
- 修改：`src/at_flow/cli.py`
- 测试：`tests/test_runtime_contracts.py`
- 测试：`tests/test_cli_controls.py`
- 文档：`docs/runtime-contracts.md`

**接口：**
- 产出：`abort_session(session: SessionState, reason: str) -> None`
- 产出：`reset_downstream_steps(session: SessionState, from_index: int) -> None`
- 产出：CLI 命令 `abort`、`reroute`

- [ ] **步骤 1：写失败测试**

新增测试，断言：

- `abort_session()` 会把 queued/running/retrying steps 标记为 aborted
- `reset_downstream_steps()` 保留上游 done step，重置选中 step 和下游 steps

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_runtime_contracts
```

预期失败：

```text
NameError: name 'abort_session' is not defined
```

- [ ] **步骤 3：实现 transition helper**

`abort_session()`：

- session 状态变为 `aborted`
- 写入 reason
- 非 done steps 变为 aborted
- 写入 finished time

`reset_downstream_steps()`：

- 从指定 index 开始清空 timestamps
- 清空 artifact path
- 清空 error/failure reason
- 清空 input paths
- 重算 session status

- [ ] **步骤 4：增加 CLI 控制**

新增：

```text
abort <session-id> --reason <reason>
reroute <session-id> --from <agent>
```

- [ ] **步骤 5：验证任务 10**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_runtime_contracts tests.test_cli_controls
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 11：Approval Guard

**文件：**
- 新增：`src/at_flow/approvals.py`
- 修改：`src/at_flow/workspace.py`
- 修改：`src/at_flow/cli.py`
- 修改：`src/at_flow/engine.py`
- 测试：`tests/test_approvals.py`
- 文档：`docs/runtime-contracts.md`
- 文档：`README.md`

**接口：**
- 产出：`ApprovalRequest`
- 产出：`create_approval(workspace: ATWorkspace, session_id: str, action: str, risk: str, command: str) -> ApprovalRequest`
- 产出：`confirm_approval(workspace: ATWorkspace, token: str) -> ApprovalRequest`
- 产出：`consume_approval(workspace: ATWorkspace, token: str, session_id: str, action: str) -> ApprovalRequest`
- 产出：CLI 命令 `approval list`、`confirm`

- [ ] **步骤 1：写失败测试**

创建 `tests/test_approvals.py`，覆盖：

- 创建 approval request
- confirm token
- consume token
- 第二次 consume 同一个 token 必须失败
- token 必须绑定 session 和 action

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_approvals
```

预期失败：

```text
ModuleNotFoundError: No module named 'at_flow.approvals'
```

- [ ] **步骤 3：实现 approval 存储**

创建：

```text
.at/approvals/pending/
.at/approvals/used/
```

approval JSON 至少包含：

- `schema_version`
- `token`
- `session_id`
- `action`
- `risk`
- `command`
- `status`
- `created_at`
- `confirmed_at`
- `used_at`
- `expires_at`

- [ ] **步骤 4：增加 CLI 命令**

新增：

```text
approval list
confirm <token>
```

对话别名：

```text
AT: confirm <token>
```

- [ ] **步骤 5：写入 timeline 和 trace**

create、confirm、consume 都写 trace。若存在 active topic，则追加 kind 为 `approval` 的 timeline entry。

- [ ] **步骤 6：验证任务 11**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_approvals
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 12：Provider Capability 检查

**文件：**
- 新增：`src/at_flow/provider_checks.py`
- 修改：`src/at_flow/cli.py`
- 测试：`tests/test_provider_checks.py`
- 文档：`README.md`

**接口：**
- 产出：`ProviderCheck`
- 产出：`check_provider_capability(name: str, config: dict[str, Any]) -> ProviderCheck`
- 产出：CLI 命令 `providers`

- [ ] **步骤 1：写失败测试**

创建 `tests/test_provider_checks.py`，使用一个不存在的 executable config，断言：

- `available is False`
- `reason` 包含 `command not found`

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_provider_checks
```

预期失败：

```text
ModuleNotFoundError: No module named 'at_flow.provider_checks'
```

- [ ] **步骤 3：实现 provider checks**

process provider 使用 `shutil.which()` 检查 executable。mock provider 不需要 command 检查。检查命令不能执行 provider。

- [ ] **步骤 4：增加 CLI 命令**

新增：

```text
providers
```

输出 provider name、type、command、availability。

- [ ] **步骤 5：验证任务 12**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_provider_checks
$env:PYTHONPATH='src'; python .\at.py providers
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 13：端到端场景测试

**文件：**
- 新增：`tests/test_e2e_scenarios.py`
- 修改：`tests/test_context_memory_contracts.py`
- 修改：`tests/test_sandbox.py`
- 文档：`docs/runtime-contracts.md`

**接口：**
- 只消费公开 runtime 和 CLI 行为。
- 产出覆盖 topic、session、context、memory、approval、retry、audit、rendering 的回归场景。

- [ ] **步骤 1：写多 session + topic 场景**

创建 `tests/test_e2e_scenarios.py`，场景：

- 初始化 workspace
- 创建 topic A 和 topic B
- 切换 active topic
- 创建两个 sessions
- 每个 session 跑一个 mock step
- 断言 context 和 handoff 保持 session-local
- 断言 active topic 保持为选中的 topic

- [ ] **步骤 2：写 save-session timeline 场景**

场景：

- 创建 topic
- 运行 mock session
- 保存 session archive
- 断言 archive 存在
- 断言 timeline 包含 session id
- 断言 panel 显示 recent timeline

- [ ] **步骤 3：写 approval 场景**

场景：

- 创建 approval
- confirm token
- consume token
- 断言第二次 consume 失败
- 断言 timeline 记录 approval

- [ ] **步骤 4：验证任务 13**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_e2e_scenarios
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

### 任务 14：对话框 ASCII Polish

**文件：**
- 修改：`src/at_flow/render.py`
- 修改：`src/at_flow/codex_trigger.py`
- 修改：`README.md`
- 测试：`tests/test_render.py`
- 测试：`tests/test_codex_trigger.py`

**接口：**
- 消费：session status、active topic、recent timeline、trace/audit/artifact 可用性。
- 产出：更清晰的 `panel --format chat`、`status --format chat` 和 Codex trigger instructions。

- [ ] **步骤 1：写失败 render 测试**

在 `tests/test_render.py` 新增测试：

- `render_chat_panel(active_topic_name="AT Runtime", recent_timeline=["16:20 context contract"])`
- 断言包含 `AT STATE MACHINE`
- 断言包含 `AT Runtime`
- 断言包含 `Recent Timeline`
- 断言 AT 状态机出现在 Codex Execution Layer 之前

- [ ] **步骤 2：运行测试并确认失败**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_render
```

预期失败：

```text
TypeError: render_chat_panel() got an unexpected keyword argument
```

- [ ] **步骤 3：更新 panel/status 顺序**

固定顺序：

```text
AT Control Panel
AT State Machine
Topic Summary
Recent Timeline
Current Session
Command Menu
Runtime Evidence
Codex Execution Layer
```

- [ ] **步骤 4：更新 Codex trigger**

`src/at_flow/codex_trigger.py` 必须指示 Codex：

```text
Always show AT state machine first, then topic/timeline context, current stage, runtime evidence, and Codex execution layer last.
```

- [ ] **步骤 5：验证任务 14**

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_render tests.test_codex_trigger
$env:PYTHONPATH='src'; python .\at.py panel --format chat
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

预期：

```text
OK
```

---

## 执行规则

- 必须按数字顺序执行任务。
- 任务 1 验证通过前，不开始专题 runtime。
- 任务 2 验证通过前，不开始时间线归档。
- topic context 存在前，不开始 SOP/persona。
- 任务 1-13 验证通过前，不开始 ASCII polish。
- 验证失败时停留在当前任务，修好后再继续。
- 文档更新必须放在改变行为的同一个任务里。
- 每次开发汇报必须包含实际运行的命令和结果。

## 全计划最终验证

运行：

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
$env:PYTHONPATH='src'; python -m compileall src tests at.py
$env:PYTHONPATH='src'; python .\at.py panel --format chat
$env:PYTHONPATH='src'; python .\at.py --help
```

预期：

```text
所有 unittest 通过
compileall exit 0
panel 在可用时显示 AT ASCII 状态机、topic 和 recent timeline
help 列出已实现命令
```

## 自检

设计覆盖：

- Topic mode：任务 2、3、4、13、14
- Timeline memory：任务 3、7、11、13、14
- Session archive：任务 3
- SOP routing：任务 5
- Persona overlay：任务 6
- Context governance：任务 4
- Memory proposal review：任务 7
- Artifact / handoff validation：任务 8
- Observability：任务 9
- Recovery / retry / abort / reroute：任务 1、10
- Approval guard：任务 11
- Provider safety：任务 12
- E2E confidence：任务 13
- 白泽式人与系统交互：任务 14

计划质量：

- 中文版和英文版路径固定。
- 每个任务都有文件、接口、步骤、测试命令和验收标准。
- runtime 与安全能力排在 UI polish 前面。
- persona 和 SOP 明确不能覆盖 `permissions.json`。
