# 专题模板（task-template）

> 创建专题时按此模板组织任务级记忆内容。
> 存储位置：`memory://task/<NNN>-<slug>/medium`（AT 记忆层管理，物理文件 `.agent/memory/medium/task-<id>.md`）

## task-id 规则

`<3位序号>-<英文短横线slug>`，如 `001-demo`、`008-fix-beam`。
序号 = 现有最大序号 +1（查 `at memory view`），无则从 `001` 开始。

## conclusion 模板句式（三要素）

```
目标：<一句话说清做什么>
范围：<涉及的模块/文件/系统>
验收：<可验证的完成标准>
```

### 示例（好）

```
conclusion: "目标：实现订单导出功能；范围：src/order/ + tests/；验收：导出 CSV 格式正确、单测全过"
```

### 反例（差）

```
conclusion: "改造 xiaot"   # 无目标/范围/验收，无法判断完成
```

## constraint 写法

- 硬约束逐条列出（如"不改 AT 记忆层"、"双生态通用"）
- 示例：`--constraint "不引入 SQLite 依赖" --constraint "skill 内容可移植"`

## unresolved 写法

- 未决问题/风险逐条列出
- 示例：`--unresolved "宿主 skill 清单需新会话验证"`

## 产出物约定

- 计划文档：`docs/superpowers/plans/YYYY-MM-DD-<feature>.md`
- 产出目录（可选）：`docs/<NNN>-<slug>/`（不强制，避免双轨存储）
- 阶段完成：`at memory add memory://session/<阶段>-<task-id>/short --conclusion "<结论>" --task <task-id>` + `at memory checkpoint`

## 生命周期（v3.0 严格动词）

`candidate`（`at memory add`，short 必绑 task）→ `verified`（`at memory verify --evidence`）
→ `settle` 分类 → 人工 `promote --confirmed --evidence --distilled` / `settle --confirmed --discard <id>` →
`archived`（`settle --apply` 自动归档纯过程记录，或 `archive` legacy 通道）
