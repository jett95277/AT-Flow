# xiaot\bin\xiaot-memory.ps1 — 薄记忆命令（v3.1 自包含）
# 用法：xiaot-memory.ps1 memory view
#       xiaot-memory.ps1 memory add memory://session/<stage>-<task>/short --conclusion "..." --task T1
# 在 ProjectRoot 下执行 `python -m xiaot_memory`，PYTHONPATH 指向本仓/部署版 xiaot_memory 模块。
# 不再解析 at 二进制：小T 记忆引擎已内迁 xiaot_memory（记忆语义与 AT 完全一致）。

param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$MemoryArgs
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\lib\xiaot-env.ps1')

if (-not $Xiaot.PythonExe) {
  throw 'xiaot-memory 未找到可用 python（需要 PyYAML）：设置环境变量 XIAOT_PYTHON，或 pip install pyyaml'
}
if ($Xiaot.ProjectRoot) { Set-Location $Xiaot.ProjectRoot }
$env:PYTHONPATH = $Xiaot.PyModule

& $Xiaot.PythonExe -m xiaot_memory @MemoryArgs
exit $LASTEXITCODE
