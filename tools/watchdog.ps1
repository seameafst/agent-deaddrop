# 看门狗：服务或隧道掉线时自动拉起（由计划任务每 10 分钟触发）
#
# 隧道后端自动识别：
#   data\cloudflared-token.txt 存在 -> 检查 cloudflared
#   否则                          -> 检查 ngrok
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$logFile = Join-Path $root "data\watchdog.log"
$cfMode = Test-Path (Join-Path $root "data\cloudflared-token.txt")

function Write-Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    $dir = Split-Path -Parent $logFile
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function Test-TunnelProcess {
    if ($cfMode) {
        return ((Get-Process cloudflared -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0)
    }
    return ((Get-Process ngrok -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0)
}

# 1) 健康检查：本地服务 + 隧道进程
$serviceOk = $false
try {
    $h = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 6
    $serviceOk = ($h.status -eq "ok")
} catch { $serviceOk = $false }

$tunnelOk = Test-TunnelProcess

if ($serviceOk -and $tunnelOk) { exit 0 }

$backend = if ($cfMode) { "cloudflared" } else { "ngrok" }
Write-Log "异常：服务健康=$serviceOk 隧道进程=$tunnelOk（后端=$backend）-> 尝试拉起"

# 2) 拉起（start_all.ps1 内部：隧道没起就起隧道，服务没起就起服务）
$start = Join-Path $root "tools\start_all.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $start 2>&1 | ForEach-Object {
    $t = [string]$_.ToString().Trim()
    if ($t) { Write-Log "  start_all: $t" }
}

# 3) 复核
Start-Sleep -Seconds 3
$nowOk = $false
try {
    $h2 = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 8
    $nowOk = ($h2.status -eq "ok")
} catch { $nowOk = $false }
$tunnelNow = Test-TunnelProcess

if ($nowOk -and $tunnelNow) {
    Write-Log "恢复成功：服务=ok 隧道=$tunnelNow"
    exit 0
} else {
    Write-Log "恢复未成功：服务=$nowOk 隧道=$tunnelNow（下次触发再试）"
    exit 1
}
