# AT V1.9 Dual Entry And One Click Setup Design

## Goal

V1.9 收尾：让 AT Flow 作为一个整体可正常使用，两个官方入口都能跑通，
并提供完整的一键配置脚本，覆盖环境检查、依赖安装、工作区初始化、
Codex 对话触发安装、Provider 配置校验与全局 opencode 配置的幂等补全，
以及双入口的一键启动与自检。

本项目定位为个人辅助开发工具流，不是产品。一键脚本服务于开发者本人，
追求可解释、幂等、可验证，不做营销式引导。

## Version Boundary

V1.9 收尾拥有：

- `scripts/setup.py` + `setup.cmd` 一键脚本（check / install / start / doctor / all）。
- Codex 对话入口的 AGENTS.md 触发块安装（`at.py enable` 的脚本化调用）。
- at.config.json 中 codex / opencode 非交互命令的幂等校验与修复。
- opencode 全局配置（`~/.config/opencode/opencode.jsonc`）在缺失项上的幂等补全：
  deepseek provider 模型 + 当前项目 `.at/shared` 与 `.at/sessions` 的
  `external_directory` 允许规则。
- 双入口启动：uvicorn 后端(:8000) + vite dev 前端(:3000)，日志、健康轮询、
  浏览器打开、统一停止。
- 双入口端到端真实验证（CLI 全流程、Web 全流程、语言契约）。

V1.9 收尾不拥有：

- 修改 Web 入口形态（保持后端 + vite dev 双进程，不做后端静态托管）。
- V1.7 云部署拓扑或 systemd/nginx 脚本（`deploy/` 已存在，不动）。
- 新增 provider（如 OpenAI API provider）。
- 长连接流式执行、任务市场等未规划能力。

## 双入口定义与就绪标准

### 入口 A：Codex 对话模式

用户在该项目内打开 Codex 对话，输入 `AT` 或 `AT:` 触发。就绪标准：

1. 项目根存在 `AGENTS.md`，且包含 `AT_FLOW_TRIGGER_BEGIN/END` 触发块。
2. `python at.py panel --format chat` 可执行并输出 AT 状态面板。
3. `python at.py start "<task>" --provider <provider> --run` 可创建并推进会话。

### 入口 B：Web Console 模式

用户通过浏览器访问 `http://127.0.0.1:3000/runtime`。就绪标准：

1. 后端 `python -m at_flow.web --root <root> --port 8000` 健康（`/api/health`）。
2. 前端 vite dev server(:3000) 可访问，且默认 API 指向 `http://localhost:8000`。
3. 页面可创建会话、运行一步/继续、查看状态机/trace/audit/artifact/语言契约，
   可切换 CodeAgent（mock / codex / opencode / auto）。

## 一键脚本设计

### 结构

```text
src/at_flow/setup.py     核心逻辑（可 import、可单测）
scripts/setup.py         薄 CLI 入口（argparse）
setup.cmd                根目录 Windows 包装（@python "%~dp0scripts\setup.py" %*）
tests/test_setup.py      核心逻辑单元测试
```

核心逻辑放在 `src/at_flow/setup.py` 而不是直接堆在 `scripts/setup.py`，
因为需要被单元测试导入，且与 runtime 模块同级便于复用 `ATWorkspace`、
`doctor_checks` 等既有能力。

### 命令

```text
python scripts/setup.py check              # 只读体检，逐项报告
python scripts/setup.py install [--skip-build] [--skip-frontend]
python scripts/setup.py start [--backend-port 8000] [--frontend-port 3000]
python scripts/setup.py doctor
python scripts/setup.py all                # check -> install -> doctor
```

### check 检查项

1. Python 可执行且版本满足实际运行要求（>=3.9，与依赖实测一致）。
2. node / npm 可用（Windows 下识别 `npm.cmd`，避开 PowerShell 执行策略）。
3. codex / opencode 命令可解析（`shutil.which`）。
4. Python 依赖 fastapi / uvicorn / httpx 可 import。
5. `.at` 工作区已初始化（`ATWorkspace.require` 成功）。
6. 项目根 `AGENTS.md` 含触发块。
7. at.config.json 中 codex 命令含 `exec ... -`、opencode 命令为 `opencode run`。
8. opencode 全局配置存在且包含 deepseek provider 与本项目 external_directory 规则。

每项输出 `OK` / `MISSING` / `FIXABLE` / `ERROR` 及修复提示；check 只读不修改。

### install 步骤（全部幂等）

1. **Python 依赖**：尝试 import 三个包；缺失时 `python -m pip install -r requirements.txt`。
2. **前端依赖**：`web/node_modules` 缺失时 `npm ci`（Windows 用 `npm.cmd`）。
3. **前端构建**：`npm run build`，`--skip-build` 跳过（本地 dev 模式不需要）。
4. **工作区**：`ATWorkspace.require` 失败则 `ATWorkspace.init`（`write_default_config`
   已确认幂等，不覆盖既有 at.config.json）。
5. **Codex 触发块**：`install_codex_trigger(ROOT)`（复用现有实现，幂等追加/替换）。
6. **at.config.json 命令修复**：codex 命令缺 `exec` 参数序列或 opencode 命令缺
   `run` 时，补为非交互形式；保留其余键；写回前校验 JSON。
7. **opencode 全局配置补全**：见下节。

### opencode 全局配置幂等补全

目标路径：`Path.home() / ".config" / "opencode" / "opencode.jsonc"`。

规则：

- 文件不存在：写入模板（deepseek provider + `deepseek-v4-flash` 模型 +
  `external_directory` 允许规则，规则路径用当前项目绝对路径生成）。
- 文件存在且可被 `json.loads` 解析（当前项目文件无注释）：深合并——
  只补缺失的 provider/model 键和当前项目的 `external_directory` 规则，
  不删除、不覆盖已有键；写回保留原有内容结构。
- 文件存在但解析失败（含注释等合法 JSONC 场景）：不静默处理，明确提示
  用户手动编辑，并给出期望内容片段（不降级）。

### start 行为

1. 先执行一次轻量 check，缺失关键项时报错并提示先跑 `install`。
2. `Popen` 启动后端：`[python, "-m", "at_flow.web", "--root", str(ROOT),
   "--host", "127.0.0.1", "--port", "8000"]`，`PYTHONPATH=src`，
   stdout/stderr 分别写 `.at/web-backend.stdout.log` / `.at/web-backend.stderr.log`。
3. `Popen` 启动前端：`npm.cmd run dev`（cwd=`web`），日志写
   `.at/web-frontend.stdout.log` / `.at/web-frontend.stderr.log`。
4. 轮询 `/api/health` 直至就绪（超时报错并打印后端日志尾部）；前端端口
   以 TCP 连通为就绪信号。
5. `webbrowser.open("http://127.0.0.1:3000/runtime")`。
6. 主循环等待；Ctrl+C / Enter 时统一 terminate 两个子进程后退出。

### doctor 与就绪报告

`doctor` 复用 `at.py doctor` 输出，叠加：

- 后端 `/api/health` HTTP 状态；
- 前端端口连通性；
- 双入口使用说明（Codex 对话：输入 `AT`；Web：`http://127.0.0.1:3000/runtime`）。

## 错误处理与兜底策略（不静默降级）

- 环境缺项：check 明确标红并给出修复命令；install 缺关键工具时报错退出。
- 依赖安装失败：报错退出，不假装成功。
- provider 命令不可用（codex/opencode 未安装）：AT 本体与 Web UI 仍可用
  （mock provider），Web 的 provider 状态按 v1.9 机制显示 unavailable 与 detail；
  一键脚本明确报告，不静默替换为 mock。
- opencode 全局配置无法解析：提示用户手动处理，不做破坏性重写。
- 启动失败：打印对应进程日志尾部，退出码非 0。

## 验证标准

1. 后端全量测试通过（现有 129 + 新增 setup 测试）。
2. 前端全量测试通过（38）与生产构建通过。
3. CLI 入口：mock/codex/opencode 各跑通一个会话或步骤（codex/opencode 需
   已配置 API；无法联网时明确标注未验证项）。
4. Web 入口：后端健康、前端可访问、创建/运行/查看闭环可用。
5. 语言契约：中文任务输入 -> 英文 runtime prompt -> 中文前端展示。
6. `setup.py check` 全绿；`install` 重复执行不产生破坏性变更（幂等）。
