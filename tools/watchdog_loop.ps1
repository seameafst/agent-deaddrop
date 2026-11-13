# 看门狗常驻循环（由 watchdog_loop.vbs 以隐藏方式启动，不产生任何窗口）
#
# 为什么不用计划任务：
#   本机 Task Scheduler 的任务文件夹 ACL 异常，连管理员都 Register/Set 被拒绝。
#   改用「登录自启 + 隐藏常驻循环」：wscript 启动 → PowerShell 隐藏运行 →
#   每 10 分钟跑一次看门狗，每 6 小时刷新一次本地数据集。
param(
    [int]$IntervalSeconds = 600,
    [int]$DatasetEveryHours = 6,
    [int]$WatchEveryHours = 24,
    [switch]$Once
)

$ErrorActionPreference = "Continue"
$tools = $PSScriptRoot
$watchdog = Join-Path $tools "watchdog.ps1"
$watchScript = Join-Path $tools "promotion_watch.py"
$root = Split-Path -Parent $tools
$logDir = Join-Path $root "data"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$loopLog = Join-Path $logDir "watchdog-loop.log"
$py = Join-Path $root ".venv\Scripts\python.exe"
$exporter = Join-Path $tools "export_public.py"
$dataset = Join-Path $root "dataset\public-export.json"

function Write-LoopLog([string]$msg) {
    try {
        Add-Content -Path $loopLog -Encoding UTF8 -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg)
    } catch { }
}

Write-LoopLog ("loop started (pid={0}, interval={1}s, dataset every {2}h)" -f $PID, $IntervalSeconds, $DatasetEveryHours)

$iteration = 0
$lastDataset = Get-Date
$lastWatch = Get-Date

while ($true) {
    try {
        # 用隐藏方式启动看门狗子进程并等待，避免它弹出任何窗口
        $p = Start-Process -FilePath "powershell.exe" `
            -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", "`"$watchdog`"" `
            -WindowStyle Hidden -PassThru -Wait
        if ($p.ExitCode -ne 0) { Write-LoopLog ("watchdog finished (exit={0})" -f $p.ExitCode) }
    } catch {
        Write-LoopLog ("watchdog error: {0}" -f $_.Exception.Message)
    }

    # 数据集刷新（默认每 6 小时）：抓本地接口、记录公网站点地址
    if ($DatasetEveryHours -gt 0 -and (Test-Path $py) -and (Test-Path $exporter)) {
        if (((Get-Date) - $lastDataset).TotalHours -ge $DatasetEveryHours) {
            try {
                $out = & $py -X utf8 $exporter --from-api "http://127.0.0.1:8000" --site "https://wirehush.com" --out $dataset --pretty 2>&1
                Write-LoopLog ("dataset refreshed: {0}" -f (($out | Select-Object -Last 1) -replace '\s+', ' '))
                $lastDataset = Get-Date
            } catch {
                Write-LoopLog ("dataset refresh failed: {0}" -f $_.Exception.Message)
            }
        }
    }

    # 推广观测哨兵（默认每天一次）：即使 DSH 会话没开，日志也在积累
    if ($WatchEveryHours -gt 0 -and (Test-Path $py) -and (Test-Path $watchScript)) {
        if (((Get-Date) - $lastWatch).TotalHours -ge $WatchEveryHours) {
            try {
                $w = & $py -X utf8 $watchScript 2>&1
                $code = $LASTEXITCODE
                $summary = ($w | Where-Object { $_ -match '公开留言|解锁|无变化' } | Select-Object -First 2) -join ' | '
                Write-LoopLog ("promotion watch (exit={0}): {1}" -f $code, ($summary -replace '\s+', ' '))
                $lastWatch = Get-Date
            } catch {
                Write-LoopLog ("promotion watch failed: {0}" -f $_.Exception.Message)
            }
        }
    }

    $iteration++
    if ($Once) { break }
    Start-Sleep -Seconds $IntervalSeconds
}

Write-LoopLog "loop stopped"
