# 看门狗：服务或隧道掉线时自动拉起（由计划任务每 10 分钟触发）
#
# 隧道后端自动识别：
#   data\cloudflared-token.txt 存在 -> 检查 cloudflared（并且检查公网可达性）
#   否则                          -> 检查 ngrok
#
# 注意：只看"进程存在"是不够的——cloudflared 进程可以活着但隧道连接已掉
#       （Cloudflare 侧显示 down / 0 connections），此时公网返回 530/000。
#       所以 cloudflared 模式下必须再做一次公网 /health 探测。
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$logFile = Join-Path $root "data\watchdog.log"
$tokenFile = Join-Path $root "data\cloudflared-token.txt"
$domainFile = Join-Path $root "data\cloudflared-domain.txt"
$cfMode = Test-Path $tokenFile

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

function Get-CloudflaredExe {
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @("$env:ProgramFiles\cloudflared\cloudflared.exe", "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe")) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Test-PublicHealth {
    if (-not (Test-Path $domainFile)) { return $true }
    $domain = (Get-Content $domainFile -Raw).Trim()
    if (-not $domain) { return $true }
    for ($i = 0; $i -lt 4; $i++) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing "https://$domain/health" -TimeoutSec 15
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Seconds 5
    }
    return $false
}

function Test-Internet {
    # 区分"隧道掉线"和"本机外网断了"——后者重启隧道也没用
    try {
        $r = Invoke-WebRequest -UseBasicParsing "https://www.baidu.com" -TimeoutSec 10
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Restart-Cloudflared {
    $exe = Get-CloudflaredExe
    if (-not $exe) { Write-Log "找不到 cloudflared.exe"; return $false }
    Get-Process cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force } catch {}
    }
    Start-Sleep -Seconds 2
    $env:TUNNEL_TOKEN = (Get-Content $tokenFile -Raw).Trim()

    # 注意：非交互上下文里 -WindowStyle 可能让 Start-Process 失败，导致"杀了拉不起来"。
    # 先试 Minimized，失败就退回不带窗口样式。
    $started = $false
    try {
        $p = Start-Process -FilePath $exe -ArgumentList @("tunnel", "run") -WindowStyle Minimized -PassThru -ErrorAction Stop
        $started = $true
    } catch {
        try {
            $p = Start-Process -FilePath $exe -ArgumentList @("tunnel", "run") -PassThru -ErrorAction Stop
            $started = $true
        } catch {
            Write-Log "Start-Process 失败: $($_.Exception.Message)"
        }
    }
    if (-not $started) { return $false }

    for ($i = 0; $i -lt 6; $i++) {
        Start-Sleep -Seconds 3
        $n = (Get-Process cloudflared -ErrorAction SilentlyContinue | Measure-Object).Count
        if ($n -gt 0) { return $true }
    }
    return $false
}

# 1) 本地服务 + 隧道进程
$serviceOk = $false
try {
    $h = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 6
    $serviceOk = ($h.status -eq "ok")
} catch { $serviceOk = $false }

$tunnelOk = Test-TunnelProcess
$backend = if ($cfMode) { "cloudflared" } else { "ngrok" }

if ($serviceOk -and $tunnelOk) {
    # 2) cloudflared：进程在也要验证公网真的通
    if ($cfMode -and -not (Test-PublicHealth)) {
        if (-not (Test-Internet)) {
            Write-Log "公网不可达，但本机外网也不通 —— 疑似本地网络问题，本轮不重启"
            exit 0
        }
        Write-Log "进程在但公网不可达（隧道连接掉线）-> 重启 cloudflared"
        if (Restart-Cloudflared) {
            if (Test-PublicHealth) { Write-Log "重启后公网恢复 OK"; exit 0 }
            Write-Log "重启后公网仍不可达，下次再试"
            exit 1
        }
        Write-Log "cloudflared 重启失败"
        exit 1
    }
    exit 0
}

Write-Log "异常：服务健康=$serviceOk 隧道进程=$tunnelOk（后端=$backend）-> 尝试拉起"

# 3) 拉起（start_all.ps1 内部：隧道没起就起隧道，服务没起就起服务）
$start = Join-Path $root "tools\start_all.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $start 2>&1 | ForEach-Object {
    $t = [string]$_.ToString().Trim()
    if ($t) { Write-Log "  start_all: $t" }
}

# 4) 复核
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
