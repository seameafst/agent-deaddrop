# 数据集自动刷新：抓公开端点 -> 隐私自检 -> 上传到 GitHub
#
# 为什么不用 GitHub Actions：创建 workflow 文件需要 token 具备 workflow scope；
# 而本机到 GitHub 的网络时通时断，本地脚本可以反复重试，且完全不需要额外权限。
#
# 上传有两条通道，互为备份：
#   1) GitHub API（gh api PUT contents）
#   2) git commit + push
# 内容没变化时直接跳过，不制造空提交。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\refresh_dataset.ps1
#   ... -Site https://your-site -MaxAttempts 20
#   ... -Local            # 强制用本地库模式（全量，需本机数据库）
#   ... -Force            # 内容没变也照样上传
param(
    [string]$Site = "https://pork-capricorn-gulp.ngrok-free.dev",
    [string]$Repo = "seameafst/agent-deaddrop",
    [int]$MaxAttempts = 12,
    [switch]$Local,
    [switch]$Force
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
# 让 Python 子进程输出 UTF-8，避免计划任务上下文里日志变乱码（数据文件本身一直是 UTF-8）
$env:PYTHONIOENCODING = "utf-8"
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$exportScript = Join-Path $root "tools\export_public.py"
$outFile = Join-Path $root "dataset\public-export.json"
$logFile = Join-Path $root "data\refresh.log"
$hashFile = Join-Path $root "data\last-upload.hash"

function Write-Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    $dir = Split-Path -Parent $logFile
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

Write-Log "=== 刷新开始 (site=$Site, local=$Local) ==="

# 1) 生成脱敏导出：API 模式优先，失败自动回退本地库模式（本机即数据源，不需要网络）
if ($Local) {
    & $py -X utf8 $exportScript --out $outFile --pretty 2>&1 | ForEach-Object { Write-Log "  export: $_" }
} else {
    & $py -X utf8 $exportScript --from-api $Site --out $outFile --pretty 2>&1 | ForEach-Object { Write-Log "  export: $_" }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $outFile)) {
        Write-Log "API 模式失败（隧道抖动），回退本地库模式"
        & $py -X utf8 $exportScript --out $outFile --pretty 2>&1 | ForEach-Object { Write-Log "  export(local): $_" }
    }
}
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $outFile)) {
    Write-Log "导出失败，保留上一版数据，退出"
    exit 1
}

# 2) 隐私自检：出现完整 IP 或 UA 特征串就绝不上传
$content = Get-Content $outFile -Raw -Encoding UTF8
$ipHits = [regex]::Matches($content, '\b(?:\d{1,3}\.){3}\d{1,3}\b')
if ($ipHits.Count -gt 0) {
    Write-Log "隐私自检失败：发现 $($ipHits.Count) 个 IP，已中止上传"
    exit 2
}
if ($content -match 'Mozilla/5\.0|Chrome/|GPTBot|ClaudeBot|curl/') {
    Write-Log "隐私自检失败：发现 UA 特征串，已中止上传"
    exit 2
}
Write-Log "隐私自检通过（0 IP / 0 UA 特征）"

# 3) 内容指纹：只有实质内容变化才上传（排除 exported_at 的时间戳抖动）
$stable = ($content | ConvertFrom-Json)
$stable.exported_at = ""
$stableJson = $stable | ConvertTo-Json -Depth 12 -Compress
$sha = [System.BitConverter]::ToString(
    [System.Security.Cryptography.SHA256]::Create().ComputeHash(
        [System.Text.Encoding]::UTF8.GetBytes($stableJson))).Replace("-", "")
$prev = if (Test-Path $hashFile) { (Get-Content $hashFile -Raw).Trim() } else { "" }
if ($prev -eq $sha -and -not $Force) {
    Write-Log "内容未变化（指纹 $($sha.Substring(0,12))…），跳过上传"
    exit 0
}

# 4) 通道一：GitHub API 上传（带退避重试）
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($outFile))
$msg = "chore(dataset): refresh public export ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))"
$uploaded = $false
for ($i = 1; $i -le $MaxAttempts -and -not $uploaded; $i++) {
    $remoteSha = $null
    try { $remoteSha = (& gh api "repos/$Repo/contents/dataset/public-export.json" --jq .sha 2>$null) } catch { $remoteSha = $null }
    $args = @("api", "--method", "PUT", "repos/$Repo/contents/dataset/public-export.json",
        "-f", "message=$msg", "-f", "content=$b64", "-f", "branch=main")
    if ($remoteSha) { $args += @("-f", "sha=$($remoteSha.Trim())") }
    $null = & gh @args 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) { $uploaded = $true; Write-Log "通道一（API）上传成功（第 $i 次尝试）" }
    else {
        Write-Log "通道一失败（第 $i/$MaxAttempts 次），退避重试…"
        Start-Sleep -Seconds ([Math]::Min(90, 5 * $i))
    }
}

# 5) 通道二：git commit + push（API 不通时兜底）
if (-not $uploaded) {
    Write-Log "改用通道二（git push）"
    for ($i = 1; $i -le 3 -and -not $uploaded; $i++) {
        & git add dataset/public-export.json 2>&1 | Out-Null
        & git -c user.name="seameafst" -c user.email="seameafst@users.noreply.github.com" commit -q -m $msg 2>&1 | Out-Null
        & git push -q origin main 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $uploaded = $true; Write-Log "通道二（git push）成功（第 $i 次尝试）" }
        else { Write-Log "通道二失败（第 $i/3 次），退避重试…"; Start-Sleep -Seconds (10 * $i) }
    }
}

if ($uploaded) {
    Set-Content -Path $hashFile -Value $sha -Encoding UTF8
    Write-Log "=== 刷新完成（指纹 $($sha.Substring(0,12))…）==="
    exit 0
} else {
    Write-Log "=== 两条通道都失败，本地文件已更新；下次运行会再试 ==="
    exit 3
}
