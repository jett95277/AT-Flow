## Context

xiaot v3.0 MVP 拍平架构：commands.py 薄函数直拼领域，无编排核心、无端口契约。本次按 ARCHITECTURE-v3 声明的「编排层 + 三接口」把代码提层级。纯内部重构，对外命令/JSON 不变。

现状模块：`models` / `workspace` / `memory_service` / `skill_router` / `spec_router` / `spec_adapter` / `commands`(直拼) / `timeline` / `inject` / `cli`。

## Goals / Non-Goals

**Goals:**
- 恢复独立编排核心（Orchestrator + 任务状态机）
- 落地三端口契约（MemoryService/ContextBuilder/RuntimeAdapter Protocol）
- 命令层薄化；依赖注入默认装配现实现
- 130 单测不回归；新增分层/端口测试
- 对齐 spec（orchestration/layering）：核心独立、状态机、端口、默认装配

**Non-Goals:**
- 不改对外命令集 / JSON / 记忆语义 / 工作区格式
- 不引入新依赖 / 不做 plugin 热加载（默认装配足够）
- 不改 openspec 侧 spec

## Decisions

1. **目标包结构**（xiaot/ 内分层）：
```
xiaot/
├── models.py        # Task/Result/ContextPack（保留）
├── ports.py         # Protocol：MemoryService / ContextBuilder / RuntimeAdapter
├── orchestrator.py  # 编排核心：Orchestrator.run + TaskState 状态机（用例收拢）
├── commands.py      # 编排用例/命令装配：默认装配端口，暴露 run 各用例
├── cli.py           # 应用层：argparse → commands 用例 → JSON（薄）
├── workspace.py     # 基础设施（保留，作 ports 实现/被编排核心用）
├── adapters/        # 端口实现迁移：memory_service/skill_router/spec_router/
│                    #   spec_adapter/context_builder/runtime 归位为适配器
├── timeline.py / inject.py  # 保留（运维/注入，不属编排用例路径）
```
*决策理由*：最小改动在现结构上加 ports + orchestrator 层，commands 收敛为"用例+默认装配"，避免大搬目录（对齐"以现状为基础最小重构"）。

2. **端口定义**（ports.py，对齐 spec §25）：
```python
class MemoryService(Protocol):
    def retrieve(self, task: Task) -> MemoryResult: ...
    def settle(self, task_id, candidates) -> SettleResult: ...
    def confirm(self, ...) -> ...: ...
class ContextBuilder(Protocol):
    def build(self, task, memory, skills, spec) -> dict: ...
class RuntimeAdapter(Protocol):
    def execute(self, context) -> Result: ...
```
现 `memory_service` / `commands.build_context` 等成为其默认实现（可先鸭子类型满足 Protocol，不必大改签名）。

3. **编排核心（orchestrator.py）**：`Orchestrator(memory=…, context=…, runtime=…)` 注入端口（默认=现实现）。`run_task(task)` 走状态机：planning → retrieve → plan 落盘 → ready（context 片段产出）→（执行由调用方 agent，xiaot 不拉进程——RuntimeAdapter 在 MVP 作为"回报入口"，settle 收 execution）→ completed/failed。`TaskState` 枚举程序内维护，与 workspace 产物一致。

4. **命令层薄化**：cli 每命令 → commands 用例（现 task/retrieve/settle/plan/confirm 等保持签名）→ 内部经 Orchestrator。避免 130 测试全改：commands 对外函数签名与返回保持，只把"直拼逻辑"下沉到 Orchestrator（内部重组），测试若断言行为不变则少动。

5. **依赖方向**：cli → commands(用例+装配) → orchestrator → ports ← adapters；禁止 commands 直拼领域服务细节（下沉）。

6. **迁移策略（低风险）**：先加 ports.py + orchestrator.py 骨架（含状态机），把 task 用例迁入 Orchestrator.run_task；retrieve/settle/plan/confirm 逐步下沉；保留现 commands 签名兼容旧测试，跑回归确认行为不变后，再清理冗余。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 130 测试大量断言命令行为 | 命令函数签名/返回保持不变（内部重组），先回归再清理 |
| 过度设计（为分层而分层） | 只落 3 端口 + 编排核心 + 状态机，不加多余抽象 |
| 状态机与文件产物矛盾 | 状态由产物推导兜底，程序状态仅为编排期视图 |
| 重构引入回归 | 每步迁移跑全量回归（130+），行为不变为准 |
