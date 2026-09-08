## Why

xiaot v3.0 编排 MVP 为快速跑通闭环，把架构**拍平**了：命令函数（commands.py）直接拼领域服务，无独立编排核心，spec/任务书定义的三接口（MemoryService/ContextBuilder/RuntimeAdapter）未落地为代码契约。导致：
- CLI/编排/领域逻辑混在薄函数集里，层级低、职责不清
- 任务生命周期没有独立状态机，靠工作区文件零散推断
- 跨模块直接 import 实现，不可替换、难扩展（未来多 Runtime / 换记忆实现）
- 与 ARCHITECTURE-v3 声明的「编排层 + 三接口」架构不符

本次把 xiaot 编排代码提升到与架构设计一致的层级：应用层（CLI 薄壳）→ 编排层（Orchestrator 核心状态机）→ 领域端口（三 Protocol）→ 基础设施（现实现）。纯内部架构重构，不改变编排命令的外部行为。

## What Changes

xiaot 编排包 `lib/python/xiaot/` 内部重新分层（对外 CLI 命令与 JSON 契约不变）：

- **编排层**：恢复独立 `Orchestrator` 核心（`run(task)` 生命周期状态机 planning→ready→executing→completed/failed），收拢 task/retrieve/settle 等编排用例；命令处理器只薄调用编排用例。
- **领域端口（ports）**：新增 `ports.py` 定义三个契约 `MemoryService` / `ContextBuilder` / `RuntimeAdapter`（Protocol），编排层仅依赖端口。
- **基础设施层**：现 `workspace` / `memory_service` / `skill_router` / `spec_router` / `spec_adapter` / `timeline` / `inject` 作为端口实现，经依赖注入进编排层（默认装配 = 现有实现，行为不变）。
- **应用层**：`cli.py` 只做参数解析→命令处理器→编排用例；不直接拼领域。
- 模块组织：`xiaot/{models,ports,orchestrator,commands(用例),handlers(薄),adapters(实现),...}` 或等价结构。

不改变：对外命令集与 JSON 返回、记忆 A 模型语义、workspace/记忆文件格式、注入产物。

## Capabilities

### New Capabilities
- `orchestration/layering`: 编排代码分层架构约束——编排核心独立于命令层、跨模块经端口接口、任务生命周期状态机、依赖注入默认装配不改变行为。

### Modified Capabilities
<!-- 无：既有行为 spec 不变；架构约束集中在新 capability -->

## Impact

- 重构范围：`lib/python/xiaot/`（新增 ports/orchestrator 分层，迁移现模块为实现层）
- 保留：models 数据类、workspace 格式、记忆引擎语义、注入生成、bin 壳
- 测试：既有 130 单测行为不回归；新增编排层状态机 + 端口契约 + 假实现注入测试
- 对外：CLI 命令/JSON 不变，无需用户迁移
