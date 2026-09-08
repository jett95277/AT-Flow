## Purpose

定义 xiaot 的记忆编排行为（A 模型，编排平台视角）：记忆 = 跨会话可复用知识（medium 项目/专题 + long 跨项目），任务过程信息归 `.xiaot/workspace/` 而非记忆库；记忆的提取与注入绑定任务生命周期事件，沉淀全部经人工确认。

## ADDED Requirements

### Requirement: 记忆层边界（A 模型）

xiaot 记忆层 SHALL 只承载跨会话可复用的已验证知识，分为 medium（项目级/专题级结论）与 long（跨项目稳定知识）；任务进行中的过程状态、产物与进度 SHALL 存放于任务工作区（`.xiaot/workspace/<task-id>/`），MUST NOT 进入记忆库；对短期会话记录的兼容存储 SHALL 保留但新编排侧不得写入。

#### Scenario: 过程信息不污染记忆

- **WHEN** 任务执行产生过程信息（改了哪个文件、中间步骤、临时进度）
- **THEN** 该信息存于任务工作区
- **AND** 不写入跨会话记忆库

### Requirement: 记忆作用域映射

medium 记忆 SHALL 以现有作用域组织：task（专题）与 project（项目）为 medium 的记忆归属；long 记忆归属跨项目（global）；专题结论进入 task scope，项目级结论进入 project scope。

#### Scenario: 结论归入正确作用域

- **WHEN** 任务收口提炼出已验证结论
- **THEN** 专题相关结论归 task scope、项目级结论归 project scope、跨项目稳定知识归 long(global)
- **AND** 检索时按对应作用域取用

### Requirement: 注入时机绑定任务生命周期

记忆注入 SHALL 在任务生命周期事件触发：任务开始/恢复时注入一次（该项目/专题已验证结论摘要 + 偏好 + 当前工作区摘要，引用式）；任务进行中 Agent 可**按需补充检索**；xiaot 不得在会话闲聊或非任务点持续自动注入。

#### Scenario: 开工注入一次 + 中途按需补查

- **WHEN** 任务开始（或恢复）
- **THEN** 编排注入该任务相关记忆摘要一次（引用式）
- **WHEN** Agent 任务中需要更多上下文
- **THEN** Agent 可调检索命令定点补充，而非全量重注入

### Requirement: 沉淀时机与全部人工确认

任务收口 SHALL 触发沉淀分析：xiaot 从任务产物提炼候选结论（新结论/约束/未决），与既有记忆比对（重复/冲突/需更新）并**生成建议清单**；任何结论进入 medium/long 前 SHALL 经人工确认，xiaot 不得自动提升记忆；失败/取消任务 SHALL 仅提炼已确认的事实性结论与未决，不得沉淀失败本身；长任务可在里程碑提前产出部分候选建议。

#### Scenario: 收工提炼 + 人工确认

- **WHEN** 任务成功收口
- **THEN** xiaot 生成候选结论建议清单（含与既有记忆的比对）
- **AND** 用户逐条确认后才写入 medium/long

#### Scenario: 失败任务不沉淀失败

- **WHEN** 任务失败或被取消
- **THEN** 仅提炼已确认事实与未决问题
- **AND** 失败信息记录于任务工作区与事件，不进入记忆库

### Requirement: 冲突与去重

沉淀比对 SHALL 处理重复与冲突：与既有记忆重复的候选不得重复入库（仅 supersede 时更新）；与既有记忆冲突的候选 SHALL 标记冲突并交由人工裁决，不得静默覆盖。

#### Scenario: 冲突需裁决

- **WHEN** 新候选与既有记忆结论冲突
- **THEN** 候选标记冲突状态
- **AND** 由用户裁决取舍，不自动覆盖
