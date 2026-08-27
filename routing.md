# SOP 路由表（xiaot 版）

> 触发词 → skill 映射 + 降级规则。
> 高频操作直读本表；低频操作按降级规则处理。

## 触发词 → Skill 映射

| 触发词 | Skill | 说明 |
|--------|-------|------|
| 记一下 / 记录 / 保存 | xiaot-memo | 一句话沉淀（结论/约束/未决） |
| 继续 XX / 切换 XX / 切到 XX | xiaot-continue | 恢复任务上下文 + 时间线 |
| 创建 XX 专题 / 新任务 | xiaot-topic | 定义任务级记忆（序号化） |
| 开始任务 / 开工 / 走一遍流程 | xiaot-workflow | 计划-执行-记忆沉淀全流程 |
| 打点 / 记录时间节点 / 存个档 | at-memory-checkpoint | 生命线节点 |
| 写 PRD / 产品需求文档 / 技术方案 / 设计文档 / 决策文档 / RFC | doc-coauthoring | 结构化文档协作（官方） |
| 做 HTML 报告 / 网页 artifact / 前端可视化 / 交互看板 | web-artifacts-builder | HTML 报告生成（官方） |
| 研究报告 / 竞品分析 / 电梯简报 / 商业分析 / 麦肯锡风格 PPT | mckinsey-consultant | 顾问式分析 + 报告/PPT（社区） |
| 爆款文章 / 公众号推文 / 情感故事 / 文案 | mimeng-writing | 中文爆款写作（社区） |
| 简化代码 / simplify / 重构简化 | code-simplification | 不改变行为的代码简化（社区） |
| 优化我的 prompt / 优化提示词 | directional-prompting | prompt 优化（社区） |
| 查看状态 / 状态 / tui / dashboard / 面板 | xiaot-status | 状态面板（记忆/专题/时间线/skills） |
| 整理记忆 / 记忆整理 / 清理记忆 / 管理记忆 | xiaot-memory-manage | 三层记忆整理（扫描→建议→确认→打点） |
| 研发模式 | persona_dev | 研发人设（DDD/TDD） |
| 产品模式 | persona_pm | 产品人设（JTBD/RICE） |

## 降级规则

1. **匹配到 1 个** → 直接执行对应 skill
2. **匹配到多个** → 列出候选让大哥选
3. **匹配到 0 个** → AI 按语义判断最接近的 skill；若无合适 skill 则作为普通对话处理

## 原则

- 路由只负责"派活"，不重复 skill 内部逻辑
- 报告/文档类产出建议完成后 `xiaot-memory memory checkpoint` 打点
- 新 skill 引入后必须在本表登记触发词
