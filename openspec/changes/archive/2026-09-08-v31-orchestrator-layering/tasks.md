## 1. 端口契约与状态模型

- [x] 1.1 新增 `ports.py`：定义 MemoryService / ContextBuilder / RuntimeAdapter Protocol（对齐 spec 三接口）；验证可 import、现 memory_service/build_context 鸭子类型满足
- [x] 1.2 `models.py` 增 TaskState 枚举（planning/ready/executing/completed/failed）；验证枚举与状态推导辅助的单元测试

## 2. 编排核心

- [x] 2.1 新增 `orchestrator.py`：`Orchestrator(memory, context, ...)` 注入端口（默认装配现实现），`run_task(task)` 走状态机（planning→retrieve→plan 落盘→ready 产出 context 片段→settle 收口→completed/failed）；验证正常链状态推进测试
- [x] 2.2 边界：记忆空/技能空降级、spec 判定、失败→failed（行为与现 commands 一致）；验证边界测试
- [x] 2.3 端口假实现注入测试：替换 MemoryService 假实现可驱动 Orchestrator（验证核心不依赖真实实现）

## 3. 命令层薄化

- [x] 3.1 cli/commands 迁移：task 用例改经 Orchestrator.run_task；retrieve/settle/plan/confirm 下沉编排或保持经装配；命令签名与 JSON 返回不变；验证全量回归（既有 130 + 新增）
- [x] 3.2 清理直拼：commands 不再直接拼领域细节（改经端口/编排）；验证回归

## 4. 回归与收尾

- [x] 4.1 全量测试（既有 130 + 编排层新增）全绿，行为不回归；验证
- [x] 4.2 E2E 冒烟：xiaot task/settle/confirm 命令真实链（临时项目）不回归；验证
- [x] 4.3 validate change + archive v31-orchestrator-layering（分层 spec 入主 specs）
