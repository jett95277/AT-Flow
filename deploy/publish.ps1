param(
  [Parameter(Mandatory = $true)][string]$HostName,
  [string]$SshUser = "ubuntu",
  [string]$AppDir = "/opt/at-flow",
  [string]$KeyFile = "E:\AT FLOW\AF_Flow.pem",
  [string]$DeepSeekApiKey = "",
  [string]$AllowedOrigins = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sshTarget = "${SshUser}@${HostName}"
$sshArgs = @("-i", $KeyFile, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")

$excludeArgs = @(
  "--exclude", ".git",
  "--exclude", ".at",
  "--exclude", "node_modules",
  "--exclude", "web/node_modules",
  "--exclude", ".venv",
  "--exclude", "output",
  "--exclude", ".claude",
  "--exclude", "*.log"
)

Write-Host "packing $root and syncing to ${sshTarget}:${AppDir}"
$tarArgs = @("-czf", "-", $excludeArgs, "-C", $root, ".")
$remoteCmd = "mkdir -p ${AppDir} && tar -xzf - -C ${AppDir}"

tar @tarArgs | ssh @sshArgs $sshTarget $remoteCmd
if ($LASTEXITCODE -ne 0) {
  throw "sync failed with exit code $LASTEXITCODE"
}

Write-Host "running install.sh on server"
$installEnv = ""
if ($DeepSeekApiKey) {
  $installEnv = "DEEPSEEK_API_KEY='${DeepSeekApiKey}' "
}
if ($AllowedOrigins) {
  $installEnv = "${installEnv}AT_ALLOWED_ORIGINS='${AllowedOrigins}' "
}
ssh @sshArgs $sshTarget "cd ${AppDir} && ${installEnv}sudo bash deploy/install.sh"
if ($LASTEXITCODE -ne 0) {
  throw "install.sh failed with exit code $LASTEXITCODE"
}
