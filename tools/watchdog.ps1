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
$apiTokenFile = Join-Path $root "data\cloudflare-api-token.txt"
$cfMode = Test-Path $tokenFile

# 隧道的权威标识（不是密钥，可以硬编码）
$CF_ACCOUNT = "4facc0af2b650c5ef206ca1a83e98cdb"
$CF_TUNNEL = "c5ae7d2e-9061-4502-b4e4-85c34ceda5b3"

function Write-Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    $dir = Split-Path -Parent $logFile
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function Get-TunnelStatusApi {
    # 用 Cloudflare API 查隧道权威状态；返回 @{status=..;connections=..}，API 不可用返回 $null。
    if (-not (Test-Path $apiTokenFile)) { return $null }
    try {
        $tok = (Get-Content $apiTokenFile -Raw).Trim()
        $uri = "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT/cfd_tunnel/$CF_TUNNEL"
        $r = Invoke-RestMethod -Uri $uri -Headers @{ Authorization = "Bearer $tok" } -TimeoutSec 20
        # 响应可能 success=false 或 result 为空（限流/令牌问题）——此时状态"未知"，不能当成"异常"
        if ($null -eq $r -or -not $r.success -or $null -eq $r.result) {
            return $null
        }
        # 只接受已知状态值，任何空/异常字符串都按"未知"处理，避免误判成"隧道异常"而误杀
        $st = ([string]$r.result.status).Trim().ToLower()
        if ($st -notin @("healthy", "degraded", "down", "inactive")) {
            return $null
        }
        $conns = 0
        if ($r.result.connections) { $conns = @($r.result.connections).Count }
        return @{ status = $st; connections = $conns }
    } catch {
        return $null
    }
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
    # 2) cloudflared：优先用 Cloudflare API 的权威状态判断（公网探测在本机常误报）
    if ($cfMode) {
        $api = Get-TunnelStatusApi
        if ($null -ne $api) {
            if ($api.status -ne "healthy" -or $api.connections -lt 1) {
                Write-Log "API 报告隧道异常（status=$($api.status), conns=$($api.connections)）-> 重启 cloudflared"
                if (-not (Restart-Cloudflared)) {
                    Write-Log "cloudflared 重启失败"
                    exit 1
                }
                Start-Sleep -Seconds 10
                $api2 = Get-TunnelStatusApi
                if ($null -eq $api2) {
                    Write-Log "重启后 API 不可达，无法判定（进程已拉起，下次再核）"
                    exit 0
                }
                if ($api2.status -eq "healthy" -and $api2.connections -ge 1) {
                    Write-Log "重启后 API 报告 healthy（conns=$($api2.connections)）"
                    exit 0
                }
                Write-Log "重启后 API 仍异常（status=$($api2.status), conns=$($api2.connections)），下次再试"
                exit 1
            }
            # API 权威判定健康 —— 不再依赖公网探测，避免本机网络抖动引发频繁重启
            exit 0
        }

        # API 不可用：退回公网探测。本机到 Cloudflare 会间歇性 000/530，
        # 单次失败不代表隧道坏了 —— 只有连续多次失败才重启，避免把好隧道弄坏。
        $counterFile = Join-Path $root "data\watchdog-fail-count.txt"
        if (Test-PublicHealth) {
            if (Test-Path $counterFile) { Remove-Item $counterFile -Force -ErrorAction SilentlyContinue }
            exit 0
        }
        if (-not (Test-Internet)) {
            Write-Log "公网不可达且本机外网也不通 —— 疑似本地网络问题，不重启"
            exit 0
        }
        $n = 0
        if (Test-Path $counterFile) {
            try { $n = [int]((Get-Content $counterFile -Raw).Trim()) } catch { $n = 0 }
        }
        $n = $n + 1
        Set-Content -Path $counterFile -Value $n -Encoding ASCII
        Write-Log "公网探测失败（连续第 $n 次，API 不可用）"
        if ($n -lt 3) {
            Write-Log "未到重启阈值（3 次），本轮先观察"
            exit 0
        }
        Write-Log "连续 $n 次失败 -> 重启 cloudflared"
        Remove-Item $counterFile -Force -ErrorAction SilentlyContinue
        if (-not (Restart-Cloudflared)) { Write-Log "cloudflared 重启失败"; exit 1 }
        if (Test-PublicHealth) { Write-Log "重启后公网恢复"; exit 0 }
        Write-Log "重启后公网仍不可达，下次再试"
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
