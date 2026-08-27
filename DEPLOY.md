# 小T 部署文档（v3.1：完全自包含，记忆引擎内迁）

> 目标：clone 独立仓库后，一条命令完成部署：13 个 skill 部署到 Codex / OpenCode，
> 并初始化 `~/.xiaot` 安装根（lib + lib\python\xiaot_memory + bin + config.json）。
> v3.1 起小T **不依赖 AT-Flow / at 二进制**——记忆引擎已内迁 `xiaot_memory`。

## 前置条件

| 依赖 | 说明 | 检查命令 |
|---|---|---|
| Python 3 + PyYAML | 记忆引擎运行环境。PyYAML 用 `pip install pyyaml`；也可用 `XIAOT_PYTHON` 指定带 PyYAML 的 python | `python -c "import yaml"` |
| PowerShell 7+ | sync 脚本运行环境 | `pwsh --version`（无 pwsh 用 powershell.exe，已兼容） |
| Git + SSH key | 拉取仓库 | `ssh -T git@github.com` 显示 Hi xxx |

> ⚠️ python 的解析顺序（见 `lib/xiaot-env.ps1`）：环境变量 `XIAOT_PYTHON` →
> PATH `python`，并校验 `import yaml`。无 PyYAML 时报错提示 `pip install pyyaml`。
> 小T 不再读取 at_command / AT_CMD（记忆引擎已内迁）。

## 部署步骤（2 步）

### 1. Clone 独立仓库

```powershell
git clone <xiaot 仓库地址>
cd <xiaot 仓库目录>
```

### 2. 一键部署 skills + 初始化 ~/.xiaot

```powershell
pwsh sync-skills.ps1
```

效果：
- `skills\` 下 **13 个 skill** 部署到 Codex（`~\.codex\skills\`）与 OpenCode（`~\.config\opencode\skills\`），带 manifest 保护
- 初始化 `~/.xiaot\`：`lib\xiaot-env.ps1`、`lib\python\xiaot_memory\`（记忆引擎快照）、`bin\xiaot-memory.ps1`、`bin\doctor.ps1`、`bin\tui.ps1`、`skills\` 快照、`config.json`（首次探测带 PyYAML 的 python）
- 若本机已装 AT-Flow 的 at 二进制，可清理 `~/.xiaot/config.json` 的 `at_command` 残留（小T 已不使用）

### 3. 验证

```powershell
# 路径诊断（XIAOT_HOME / ProjectRoot / python / 记忆自检 / skills 部署）
powershell -ExecutionPolicy Bypass -File ~\.xiaot\bin\doctor.ps1

# 状态面板
pwsh ~\.xiaot\bin\tui.ps1 -Mode text
```

应显示：记忆自检 OK、记忆统计、专题列表、13 个 Skills 部署状态（●=2/2）。

> ⚠️ 新 skill 需**新开会话**才被 Codex/OpenCode 加载。

## 在任意项目中使用（不绑定 xiaot 仓库位置）

小T 的 skill 在任意目录运行，自动定位当前项目根（向上找 `.agent` / `.xiaot`）并调用记忆命令：

```powershell
# 任意项目里（已含 .agent 的仓库，或先 init）
pwsh ~\.xiaot\bin\xiaot-memory.ps1 memory view
```

记忆命令以项目根 `.agent` 为记忆目录；无 `.agent` 时先跑 `xiaot-memory init`。

## 部署后能力（13 个 skill）

| Skill | 触发词 | 用途 |
|---|---|---|
| xiaot-memo | 记一下/记录/保存 | 一句话沉淀到记忆 |
| xiaot-continue | 继续XX/切换XX | 恢复任务上下文 |
| xiaot-topic | 创建XX专题/新任务 | 序号化任务定义 |
| xiaot-workflow | 开工/走一遍流程 | 计划-执行-沉淀（S/M/L 分级） |
| at-memory-checkpoint | 打点/存个档 | 时间线生命线 |
| xiaot-status | 查看状态/tui | 状态面板 |
| xiaot-memory-manage | 整理记忆/管理记忆 | 三层记忆整理 |
| doc-coauthoring | 写PRD/技术方案 | 文档协作（官方引入） |
| web-artifacts-builder | HTML报告/可视化 | 前端 artifact（官方引入） |
| mckinsey-consultant | 研究报告/竞品/PPT | 顾问式分析（社区） |
| mimeng-writing | 爆款文章/文案 | 中文写作（社区） |
| code-simplification | 简化代码/simplify | 代码简化（社区） |
| directional-prompting | 优化我的prompt | prompt 优化（社区） |

## 更新 skills / 安装根 / 记忆引擎

改 `skills\` 下任何 SKILL.md 或 `lib\python\xiaot_memory\` 下任何模块后：

```powershell
pwsh sync-skills.ps1
```

## 常用运维

| 操作 | 命令 |
|---|---|
| 查看状态 | `pwsh ~\.xiaot\bin\tui.ps1`（交互） / `-Mode text`（对话内） |
| 记忆整理 | 对话中说"整理记忆" |
| 专题创建 | 对话中说"创建XX专题" |
| 记忆导出 | `& $Xiaot.MemoryCmd memory export`（项目根执行） |
| 覆盖 python | 设环境变量 `XIAOT_PYTHON`（需带 PyYAML） |
| 记忆自检 | `powershell -File ~\.xiaot\bin\doctor.ps1` |

## 常见问题

| 问题 | 解决 |
|---|---|
| codex 连不上 API | 设代理后启动：`$env:HTTPS_PROXY="http://127.0.0.1:7890"; codex` |
| 新 skill 不生效 | 新开会话（skill 清单会话启动时加载） |
| sync 报权限错误 | 确保对 `~\.codex` 与 `~\.xiaot` 有写权限 |
| python 无 PyYAML | `pip install pyyaml`，或设 `XIAOT_PYTHON` 指向带 PyYAML 的 python |
| 记忆命令找不到 | `doctor.ps1` 看 PythonExe 来源；`python -m xiaot_memory` 直接验证 |
| 项目无 .agent | 项目根先跑 `xiaot-memory init` |

## 可移植性说明

- skill 内容全部走 `~/.xiaot/lib/xiaot-env.ps1` 解析环境（XIAOT_HOME / ProjectRoot / PythonExe / MemoryCmd），不依赖 workdir、不硬编码 `.venv\Scripts\at.exe`
- 记忆引擎 `xiaot_memory` 仅依赖 Python 标准库 + PyYAML，与 AT-Flow 完全解耦
- 仓库内 4 个社区引入 skill 已适配：中文触发词 + metadata(domain/source) + Anti-Patterns
- 所有外部 skill 许可：MIT / Apache 2.0 / 官方，见各目录 LICENSE 与 `skills-bundle` MANIFEST
