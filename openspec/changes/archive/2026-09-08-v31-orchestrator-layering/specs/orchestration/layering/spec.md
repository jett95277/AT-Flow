## Purpose

定义 xiaot 编排代码的分层架构约束：编排核心独立于命令层、跨模块交互经端口接口、任务生命周期有独立状态机、依赖注入默认装配不改变行为，使编排层可测试、可替换、可演进为完整 Harness。

## ADDED Requirements

### Requirement: 编排核心独立于命令层

xiaot 的任务编排核心（Orchestrator）SHALL 独立存在，承担任务生命周期编排（规划→就绪→执行→完成/失败）；命令层（CLI 处理器）SHALL 只做参数解析与结果输出，MUST NOT 直接拼装领域服务。

#### Scenario: 命令层薄调用编排核心

- **WHEN** 用户调用任一编排命令（task/retrieve/settle 等）
- **THEN** 命令处理器薄调用编排用例获取结果
- **AND** 编排逻辑不散落在命令函数内

### Requirement: 任务生命周期状态机

编排核心 SHALL 以程序内状态机推进任务：planning（规划产物未就绪）→ ready（规划就绪待执行）→ executing（交执行方）→ completed/failed（依结果）；状态 SHALL 与工作区/结果产物推导保持一致，MUST NOT 出现相互矛盾。

#### Scenario: 状态机推进与结果一致

- **WHEN** 编排核心收到执行结果
- **THEN** 任务状态转为 completed 或 failed
- **AND** 状态与落盘产物（plan/result）一致

### Requirement: 跨模块经端口接口

编排核心与外部能力（记忆、上下文构建、运行时）交互 SHALL 经端口接口（Protocol：MemoryService / ContextBuilder / RuntimeAdapter），核心 MUST NOT 直接依赖具体实现模块；更换或新增实现（如替换记忆引擎、多 Runtime）不修改编排核心。

#### Scenario: 端口契约隔离实现

- **WHEN** 编排核心需要记忆/上下文/执行能力
- **THEN** 经对应端口接口调用
- **AND** 具体实现可替换而不改核心

### Requirement: 默认装配不改变行为

分层后 SHALL 提供默认装配（以现有实现装配端口），使既有命令行为与 JSON 返回不变；分层重构 MUST NOT 改变对外契约或记忆/工作区语义。

#### Scenario: 重构后行为回归

- **WHEN** 分层重构完成
- **THEN** 既有 130 单测与编排命令行为不回归
- **AND** 对外命令集与返回结构不变
