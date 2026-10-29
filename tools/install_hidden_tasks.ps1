# 把 AgentDeadDrop 的两个计划任务改成"完全隐藏窗口"运行
#
# 背景：任务动作是 powershell.exe -File xxx.ps1，每 10 分钟会闪一个终端窗口。
#       改成 wscript.exe 调用 run_hidden.vbs 后，PowerShell 以隐藏窗口启动，不再闪。
#
# 用法：以管理员身份运行 PowerShell，然后执行
#   powershell -NoProfile -ExecutionPolicy Bypass -File "<本文件路径>"
#
# 说明：改计划任务需要管理员权限（任务由管理员创建，普通权限会 Access denied）。
param(
    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"
$tools = $PSScriptRoot
$vbs = Join-Path $tools "run_hidden.vbs"

if (-not (Test-Path $vbs)) { throw "找不到 $vbs" }

$tasks = @(
    @{ Name = "AgentDeadDrop-Watchdog";       Script = Join-Path $tools "watchdog.ps1" },
    @{ Name = "AgentDeadDrop-RefreshDataset"; Script = Join-Path $tools "refresh_dataset.ps1" }
)

Write-Host "== 当前权限 =="
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host ("  管理员: {0}" -f $isAdmin)
if (-not $isAdmin -and -not $WhatIfOnly) {
    throw "需要管理员权限：请右键 PowerShell -> 以管理员身份运行，再执行本脚本"
}

foreach ($t in $tasks) {
    $exists = Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue
    if (-not $exists) { Write-Host ("  [{0}] 不存在，跳过" -f $t.Name); continue }
    $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument ('"{0}" "{1}"' -f $vbs, $t.Script)
    if ($WhatIfOnly) {
        Write-Host ("  [{0}] 将改为: wscript.exe {1} {2}" -f $t.Name, $vbs, $t.Script)
        continue
    }
    Set-ScheduledTask -TaskName $t.Name -Action $action | Out-Null
    $now = Get-ScheduledTask -TaskName $t.Name
    Write-Host ("  ✅ [{0}] -> {1} {2}" -f $t.Name, $now.Actions.Execute, $now.Actions.Arguments)
}

Write-Host ""
Write-Host "完成。下一次触发时不应再出现窗口。"
Write-Host "如需回滚：Set-ScheduledTask -TaskName <名字> -Action (New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -ExecutionPolicy Bypass -File ""<脚本>""')"
