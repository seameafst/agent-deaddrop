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

# 定时任务的时间戳必须落盘：循环经常因为重启/重新登录而重启，
# 放在内存里会导致 24h / 6h 窗口永远到不了（11-13 之后就再没自动跑过哨兵）。
$stateFile = Join-Path $logDir ".loop-state.json"
$state = @{}
try {
    if (Test-Path $stateFile) {
        $loaded = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($k in @("lastDataset", "lastWatch")) {
            if ($loaded.$k) { $state[$k] = [datetime]$loaded.$k }
        }
    }
} catch { }

function Save-LoopState {
    try {
        $obj = @{
            lastDataset = ($(if ($state["lastDataset"]) { $state["lastDataset"].ToString("o") } else { $null }))
            lastWatch   = ($(if ($state["lastWatch"]) { $state["lastWatch"].ToString("o") } else { $null }))
        } | ConvertTo-Json
        [System.IO.File]::WriteAllText($stateFile, $obj, (New-Object System.Text.UTF8Encoding($false)))
    } catch { }
}

$iteration = 0
$lastDataset = if ($state["lastDataset"]) { $state["lastDataset"] } else { Get-Date }
$lastWatch = if ($state["lastWatch"]) { $state["lastWatch"] } else { Get-Date }
Write-LoopLog ("carried state: lastDataset={0:yyyy-MM-dd HH:mm} lastWatch={1:yyyy-MM-dd HH:mm}" -f $lastDataset, $lastWatch)

# 任何一步都可能因为网络卡死（公网探测、GitHub API）；给每步设硬超时，
# 否则一次卡死会让整个循环停在这一轮（11-21 手工测试时亲眼见过卡 6 分钟）。
function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$ArgList,
        [int]$TimeoutSec = 300,
        [string]$Tag = "step"
    )
    $outFile = Join-Path $logDir ("_step_{0}.out" -f $Tag)
    $errFile = $outFile + ".err"
    $p = Start-Process -FilePath $Exe -ArgumentList $ArgList -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile
    $done = $p.WaitForExit($TimeoutSec * 1000)
    if (-not $done) {
        try { $p.Kill() } catch { }
        Write-LoopLog ("{0}: TIMEOUT after {1}s (killed)" -f $Tag, $TimeoutSec)
        return @{ TimedOut = $true; ExitCode = -1; Output = "" }
    }
    $text = ""
    try { if (Test-Path $outFile) { $text = Get-Content $outFile -Raw -Encoding UTF8 } } catch { }
    try { Remove-Item $outFile, $errFile -Force -ErrorAction SilentlyContinue } catch { }
    $code = -1
    try {
        # Start-Process 带重定向时，ExitCode 要等流读完才可用：
        # 再调用一次无参 WaitForExit() 把异步输出刷完。
        $p.WaitForExit()
        $p.Refresh()
        if ($p.HasExited) { $code = [int]$p.ExitCode }
    } catch { }
    return @{ TimedOut = $false; ExitCode = $code; Output = $text }
}

while ($true) {
    try {
        $r = Invoke-Step -Exe "powershell.exe" `
            -ArgList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", "`"$watchdog`"") `
            -TimeoutSec 240 -Tag "watchdog"
        if (-not $r.TimedOut -and $r.ExitCode -ne 0) {
            Write-LoopLog ("watchdog finished (exit={0})" -f $r.ExitCode)
        }
    } catch {
        Write-LoopLog ("watchdog error: {0}" -f $_.Exception.Message)
    }

    # 数据集刷新（默认每 6 小时）：抓本地接口、记录公网站点地址
    if ($DatasetEveryHours -gt 0 -and (Test-Path $py) -and (Test-Path $exporter)) {
        if (((Get-Date) - $lastDataset).TotalHours -ge $DatasetEveryHours) {
            try {
                $r = Invoke-Step -Exe $py `
                    -ArgList @("-X", "utf8", $exporter, "--from-api", "http://127.0.0.1:8000",
                               "--site", "https://wirehush.com", "--out", $dataset, "--pretty") `
                    -TimeoutSec 180 -Tag "dataset"
                if ($r.TimedOut) {
                    Write-LoopLog "dataset refresh timed out"
                } else {
                    $line = ($r.Output -split "`n" | Where-Object { $_ -match '已导出' } | Select-Object -Last 1)
                    if (-not $line) { $line = ($r.Output -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 1) }
                    Write-LoopLog ("dataset refreshed (exit={0}): {1}" -f $r.ExitCode, ($line -replace '\s+', ' ').Trim())
                    $lastDataset = Get-Date
                    $state["lastDataset"] = $lastDataset; Save-LoopState
                }
            } catch {
                Write-LoopLog ("dataset refresh failed: {0}" -f $_.Exception.Message)
            }

            # 数据集新鲜度守卫：GitHub 的 schedule 经常延迟数小时甚至跳过，
            # 发现公网那份落后就手动触发 workflow_dispatch（repo scope 够用）。
            $guard = Join-Path $PSScriptRoot "dataset_guard.py"
            if (Test-Path $guard) {
                $g = Invoke-Step -Exe $py -ArgList @("-X", "utf8", $guard, "--max-age", "30") -TimeoutSec 180 -Tag "guard"
                if (-not $g.TimedOut) {
                    $gline = ($g.Output -split "`n" | Where-Object { $_ -match '结论' } | Select-Object -Last 1)
                    if ($gline) {
                        $gline = ($gline -replace '\s+', ' ').Trim()
                        if ($gline -notmatch '新鲜') {
                            Write-LoopLog ("dataset guard (exit={0}): {1}" -f $g.ExitCode, $gline)
                        }
                    }
                }
            }
        }
    }

    # 推广观测哨兵（默认每天一次）：即使 DSH 会话没开，日志也在积累
    if ($WatchEveryHours -gt 0 -and (Test-Path $py) -and (Test-Path $watchScript)) {
        if (((Get-Date) - $lastWatch).TotalHours -ge $WatchEveryHours) {
            try {
                $r = Invoke-Step -Exe $py -ArgList @("-X", "utf8", $watchScript) -TimeoutSec 180 -Tag "watch"
                if ($r.TimedOut) {
                    Write-LoopLog "promotion watch timed out"
                } else {
                    $summary = (($r.Output -split "`n") | Where-Object { $_ -match '公开留言|解锁|无变化|变化：' } | Select-Object -First 2) -join ' | '
                    Write-LoopLog ("promotion watch (exit={0}): {1}" -f $r.ExitCode, ($summary -replace '\s+', ' '))
                    $lastWatch = Get-Date
                    $state["lastWatch"] = $lastWatch; Save-LoopState
                }
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
