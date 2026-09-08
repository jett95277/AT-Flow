# xiaot\bin\xiaot.ps1 — 编排 CLI 薄壳（M5b 后真实调用入口）
# 用法：xiaot.ps1 task "重构记忆模块" --project X
#       xiaot.ps1 inject --dir <project>
# 复用 xiaot-env.ps1 解析环境（PyModule = lib/python，含 xiaot 编排包与 xiaot_memory）。

param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$XiaotArgs
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\lib\xiaot-env.ps1')

if (-not $Xiaot.PythonExe) {
  throw 'xiaot 未找到可用 python（需要 PyYAML）：设置环境变量 XIAOT_PYTHON，或 pip install pyyaml'
}
if ($Xiaot.ProjectRoot) { Set-Location $Xiaot.ProjectRoot }
$env:PYTHONPATH = $Xiaot.PyModule

& $Xiaot.PythonExe -m xiaot @XiaotArgs
exit $LASTEXITCODE
