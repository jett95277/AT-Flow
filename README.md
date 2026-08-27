# 小T（Xiaot）

**Codex / OpenCode 通用的个人 AI 助手系统（v3.1：完全自包含，记忆引擎内迁）。**

## 定位

小T 是个人开发流程里的人设与 SOP 层：定义"怎么说话、怎么记、怎么恢复"。
v3.1 起小T **完全独立**：三层记忆引擎已内迁为 `xiaot_memory` 模块，
不依赖 AT-Flow / at 二进制，clone 即可用。基于 Codex / OpenCode 通用机制
实现（AGENTS.md + SKILL.md + 薄记忆命令），同一套文件双生态可用。

## 结构

| 层 | 落地 | 说明 |
|---|---|---|
| 规则层 | `AGENTS.md` | 12 条规则 + 权限管理 + Git 工作流 |
| 定位层 | `lib/xiaot-env.ps1` + `bin/xiaot-memory.ps1` | 统一解析 XIAOT_HOME / ProjectRoot / python / 记忆命令 |
| 记忆层 | `lib/python/xiaot_memory/` | 内迁记忆引擎（三层记忆 + 治理层，复用 AT 语义） |
| 人设层 | `personas/*.md` | 全局/研发/产品三模式（charter 化） |
| SOP 层 | `skills/`（13 个 skill） | 自有 7 个 + 现成引入 6 个 |
| 路由层 | `routing.md` | 触发词→skill 路由 + 降级规则 |
| 模板层 | `templates/task-template.md` | 专题结构模板（序号化 + 目标/范围/验收） |
| 会话层 | `xiaot-memory memory checkpoint` | 记忆层生命线 |
| 启动层 | `xiaot-continue` skill | 按需恢复，不自动注入 |

## 目录结构

```text
xiaot/
├── AGENTS.md               # 规则层（Codex / OpenCode 通用）
├── routing.md              # 路由层：触发词→skill 表 + 降级规则
├── DEPLOY.md               # 部署文档（独立仓库 clone 即用）
├── sync-skills.ps1         # 一键同步 skills + 部署 ~/.xiaot 安装根
├── tui.ps1                 # 状态面板（交互 + text 双模式）
├── doctor.ps1              # 路径诊断（python + 记忆自检 + skills 部署）
├── lib/
│   ├── xiaot-env.ps1       # 定位层：导出 $Xiaot（MemoryCmd / PythonExe / ProjectRoot）
│   └── python/
│       └── xiaot_memory/   # 记忆引擎（内迁：memory/policy/settle/context/events/timeline/view）
├── bin/
│   └── xiaot-memory.ps1    # 薄记忆命令入口（python -m xiaot_memory）
├── personas/               # 人设层（charter 化）
│   ├── persona_global.md   # 全局人设
│   ├── persona_dev.md      # 研发人设
│   └── persona_pm.md       # 产品人设
├── templates/
│   └── task-template.md    # 专题结构模板
├── skills/                 # SOP 层（SKILL.md 格式）
│   ├── xiaot-memo/         # 一句话记录（自有）
│   ├── xiaot-continue/     # 恢复任务上下文（自有）
│   ├── xiaot-topic/        # 创建任务定义（自有，序号化）
│   ├── xiaot-workflow/     # 计划-执行-记忆沉淀全流程（自有，S/M/L 分级）
│   ├── at-memory-checkpoint/ # 生命线打点（自有）
│   ├── xiaot-status/       # 状态面板 TUI 入口（自有）
│   ├── xiaot-memory-manage/  # 三层记忆整理（自有）
│   ├── doc-coauthoring/    # 文档协作：PRD/技术方案/RFC（Anthropic 官方）
│   ├── web-artifacts-builder/ # HTML 报告/artifact（Anthropic 官方）
│   ├── mckinsey-consultant/  # 顾问式报告/竞品/PPT（社区 fleurytian，MIT）
│   ├── mimeng-writing/     # 中文爆款写作（社区 fleurytian，MIT）
│   ├── code-simplification/  # 代码简化（社区 addyosmani，MIT）
│   └── directional-prompting/ # prompt 优化（社区 kingbootoshi，MIT）
└── README.md
```

## 使用方式

### 部署（独立仓库 clone 即用）

详见 **[`DEPLOY.md`](DEPLOY.md)**，核心两步：

```powershell
git clone <本仓库地址> && cd xiaot
pwsh sync-skills.ps1      # 部署 13 个 skill + xiaot_memory 到 ~/.xiaot（lib/bin/skills/config.json）
```

记忆命令需要 **Python 3 + PyYAML**（`pip install pyyaml`）。可用
`XIAOT_PYTHON` 环境变量指定 python；默认取 PATH 上的 `python`。
记忆数据位于项目根 `.agent/`（已随仓库保留，不入 git）。

### Codex

读取 `xiaot/AGENTS.md` 即加载小T规则；skills 由 AGENTS 显式引用
（`xiaot/skills/<name>/SKILL.md`），也可复制到 `~/.codex/skills/` 自动发现。

### OpenCode

OpenCode 原生支持 AGENTS.md 与 Anthropic SKILL.md 格式：

- 规则：把 `xiaot/AGENTS.md` 的内容并入项目 AGENTS.md，或复制为项目根
  `AGENTS.md`（OpenCode 优先读取）
- 技能：复制 `xiaot/skills/*` 到 OpenCode 扫描目录（项目或 home）

### 记忆层（内迁，复用 AT 治理语义）

小T 自带三层记忆引擎 `xiaot_memory`：short（临时，必绑 task）→
medium（需证据 + 重提炼 + 确认）→ long（需 verified + 项目归属）。
`bin/xiaot-memory.ps1` 是统一入口，skills 一律 `& $Xiaot.MemoryCmd memory <sub>`。

### 记忆晋升示例（v3.1 严格动词）

一条 short 沉淀到 medium 的完整链路：

```powershell
# 1. 沉淀（short 必绑 task）
& $Xiaot.MemoryCmd memory add memory://session/code-001-fix-beam/short --conclusion "beam 阈值测出为 2" --task 001-fix-beam
# 2. 验证（补证据）
& $Xiaot.MemoryCmd memory verify memory://session/code-001-fix-beam/short --evidence "test:beam<2"
# 3. 结算（默认 dry-run，看分类）
& $Xiaot.MemoryCmd memory settle 001-fix-beam
# 4. 晋升（需确认 + 证据 + 重新提炼，禁复制原文）
& $Xiaot.MemoryCmd memory promote memory://session/code-001-fix-beam/short --to medium --confirmed --evidence "test:beam<2" --distilled "beam 阈值固定为 2，低于则跳过稳定性检查"
```

short 无 `--task`、medium 缺证据/未提炼/未确认、技术事实直写 long，都会被准入规则拒绝。

## 边界（诚实声明）

- 不依赖外部路由数据库（`routing.md` 做触发词路由，记忆做索引）
- 一次性审批交给宿主（Codex / OpenCode）权限机制，不在小T 内重复实现
- 不做自动欢迎语（改为按需 continue）
- `xiaot-workflow` 依赖 Superpowers（writing-plans / executing-plans 等）：
  Codex 插件内置直接可用；OpenCode 需自行安装 Superpowers 技能——可从
  Codex 插件缓存复制（`~/.codex/plugins/.../superpowers/*/skills/*`）到
  `~/.config/opencode/skills/`，或按 Superpowers 官方文档安装。
- 跨生态已由 OpenCode 官方文档确认支持 AGENTS.md 与 SKILL.md，但具体版本
  行为建议实测（最小验证：同一目录 codex / opencode 各跑一次记忆读写）
