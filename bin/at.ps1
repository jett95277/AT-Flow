# xiaot\bin\at.ps1 — 统一 at 调用入口
# 解析 $Xiaot.ATCommand 并透传参数；在 ProjectRoot 下执行。
# 用法：at.ps1 memory view   /   at.ps1 memory add <uri> --conclusion "..." --task T1
#
# 消除 6 处 `.venv\Scripts\at.exe` 硬编码：skills / doctor / tui 统一走这里或 $Xiaot.ATCommand。

param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$AtArgs
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\lib\xiaot-env.ps1')

if (-not $Xiaot.ATCommand) {
  throw 'at 命令未找到：设置环境变量 AT_CMD，或 ~/.xiaot/config.json 的 at_command，或将 at 加入 PATH'
}
if ($Xiaot.ProjectRoot) { Set-Location $Xiaot.ProjectRoot }

& $Xiaot.ATCommand @AtArgs
exit $LASTEXITCODE
