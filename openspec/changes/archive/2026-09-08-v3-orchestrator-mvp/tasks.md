## 1. 骨架与任务闭环（M1 - 完成）

- [x] 1.1 编排包骨架 `lib/python/xiaot/`（models/workspace/commands/cli/memory_service），验证 import 与 10 单测通过
- [x] 1.2 `xiaot task` 任务闭环：建 `.xiaot/workspace/<task-id>/`（plan.md/result.md/context.json）+ JSON 机器面返回，CLI 冒烟通过
- [x] 1.3 workspace 即恢复源：`task --resume` 读快照重建；未知任务明确报错
- [x] 1.4 记忆/技能/规范编排接入 task（retrieve/skill_hints/spec_decision 进 context 片段）

## 2. 记忆编排（A 模型，M2 - 完成）

- [x] 2.1 A 模型检索：只 medium{task,project}/long{global}，排除 short/session 过程（candidate_uris 不生成 short uri）
- [x] 2.2 引用式预算：inline summary 受 budget 限制，超限进 refs（total/uris）供按需读
- [x] 2.3 settle 比对 + 全人工：duplicate/review 建议 + scope 归属提示（task/project），policy=all_promotions_manual
- [x] 2.4 修复 build_memory_context entries 为 dict 的解析 bug（M1 空记忆掩盖）
- [x] 2.5 project scope 决策：引擎零改动，settle 建议归 project scope；存量 task 数据按 task uri 检索

## 3. 上下文编排（M3 - 完成）

- [x] 3.1 context 片段组装：instruction + memory_summary + memory_refs + skill_hints + spec_decision + constraints
- [x] 3.2 引用式：内联预算、超限 refs 引用、不倾倒内部库
- [x] 3.3 context 独立单测（test_m3_context：片段形态/预算/技能/规格/真实 retrieve 不倾倒）

## 4. 技能与规范编排（M4 - 完成）

- [x] 4.1 skill_router：扫领域技能 description 匹配 → skill_hints（触发词 + 前缀匹配增强）
- [x] 4.2 spec_router：启发式判定 needs_spec（light/large），规则可配
- [x] 4.3 spec_adapter：复用 spec 工作流 CLI 骨架（available/new_change/status_json + init_workspace + cwd 支持）
- [x] 4.4 spec gate 不静默：判需 spec 而 CLI 不可用 → 明确错误

## 5. 时间线与注入（M5 - 完成）

- [x] 5.1 checkpoint 升级：workspace + 记忆快照（memory_node），list/rollback（test_m5a）
- [x] 5.2 注入生成：`xiaot inject` 写 `.opencode/commands/xiaot-*` + xiaot-orchestrate driver skill（test_m5b）
- [x] 5.3 driver skill 强化：MANDATORY 强触发 + plan-then-inject 铁律（真实会话修复：旧 skill 抢先）

## 6. E2E 与真实会话（M6 - 完成）

- [x] 6.1 E2E 三链：普通任务链 / spec 链（真实 spec 复用建 change）/ 记忆生命周期（test_m6）
- [x] 6.2 真实 opencode 会话验证：skill 触发 → task/resume → checkpoint → 执行 → settle（review/scope 建议 + 全人工）全通
- [x] 6.3 真实验证修复：xiaot CLI PATH / HOME 误判项目根 / ~/.xiaot 部署根混淆 / Path.lower bug / env UTF-8 BOM
- [ ] 6.4 遗留：settle 建议的人工确认写入流程实战（大哥点 proceed 后写入 medium）
- [ ] 6.5 遗留：codex/其他 agent 注入验证；spec 任务真实跑完整 change 流程
- [ ] 6.6 遗留：全量基线回归 + 文档同步（README/DEPLOY 编排入口）

## 7. 回归

- [x] 7.1 全量单测 125 OK（旧记忆引擎 83 不回归；Python 3.9/3.12 兼容）
