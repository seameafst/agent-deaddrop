# 切换到 Cloudflare Tunnel：一条命令完成
#
# 前提：在 Cloudflare 控制台（Zero Trust -> Networks -> Tunnels）已创建隧道，
#       并已添加 Public Hostname: <域名> -> http://localhost:8000
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\cutover_cloudflare.ps1 `
#       -Token "eyJhIjoi..." -Domain wirehush.com
#
# 可选：-KeepNgrok 保留 ngrok（默认会停掉，避免两个隧道同时指向同一服务）
param(
    [string]$Token = "",
    [string]$Domain = "wirehush.com",
    [string]$Repo = "seameafst/agent-deaddrop",
    [switch]$KeepNgrok
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"

# 未在命令行给令牌时，从 data/cloudflared-token.txt 读取（避免令牌出现在命令行/历史里）
if (-not $Token) {
    $tf = Join-Path $root "data\cloudflared-token.txt"
    if (-not (Test-Path $tf)) { throw "未提供 -Token，且 data\cloudflared-token.txt 不存在" }
    $Token = (Get-Content $tf -Raw).Trim()
    Write-Host "从 data\cloudflared-token.txt 读取令牌（长度 $($Token.Length)）"
}

function Step([string]$m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok([string]$m) { Write-Host "    ✅ $m" -ForegroundColor Green }
function Warn([string]$m) { Write-Host "    ⚠ $m" -ForegroundColor Yellow }

$pub = "https://$Domain"

# ---------- 1) 校验令牌 ----------
Step "校验连接令牌"
$tok = $Token.Trim()
if ($tok.Length -lt 80) { throw "令牌太短（$($tok.Length) 字符），请确认复制完整" }
if (-not $tok.StartsWith("eyJ")) { Warn "令牌不像 cloudflared 连接令牌（通常以 eyJ 开头），继续尝试" }
Ok "令牌长度 $($tok.Length)"

# ---------- 2) 落盘（data/ 已在 .gitignore，不会提交） ----------
Step "保存令牌与域名"
$dataDir = Join-Path $root "data"
if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Force -Path $dataDir | Out-Null }
[System.IO.File]::WriteAllText((Join-Path $dataDir "cloudflared-token.txt"), $tok, (New-Object System.Text.UTF8Encoding($false)))
[System.IO.File]::WriteAllText((Join-Path $dataDir "cloudflared-domain.txt"), $Domain, (New-Object System.Text.UTF8Encoding($false)))
Ok "data\cloudflared-token.txt / cloudflared-domain.txt"

# ---------- 3) 停 ngrok，起 cloudflared ----------
Step "切换隧道后端"
if (-not $KeepNgrok) {
    Get-Process ngrok -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.Id -Force } catch {} }
    Ok "已停止 ngrok"
}
Get-Process cloudflared -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.Id -Force } catch {} }
Start-Sleep -Seconds 2

$cfExe = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cfExe) {
    foreach ($p in @("$env:ProgramFiles\cloudflared\cloudflared.exe", "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe")) {
        if (Test-Path $p) { $cfExe = $p; break }
    }
}
if (-not $cfExe) { throw "找不到 cloudflared.exe" }

$env:TUNNEL_TOKEN = $tok
Start-Process -FilePath $cfExe -ArgumentList @("tunnel", "run") -WindowStyle Minimized
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if ((Get-Process cloudflared -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) { break }
}
if ((Get-Process cloudflared -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) { throw "cloudflared 未启动（令牌可能无效）" }
Ok "cloudflared 已在运行"

# ---------- 4) .env：公网地址 + Cloudflare 来源 IP 头 ----------
Step "更新 .env"
$envFile = Join-Path $root ".env"
$lines = @()
if (Test-Path $envFile) {
    $lines = Get-Content $envFile -Encoding UTF8 | Where-Object {
        $_ -notmatch '^\s*#?\s*(PUBLIC_BASE_URL|MCP_SELF_URL|TRUSTED_IP_HEADER)\s*='
    }
}
$lines += "PUBLIC_BASE_URL=$pub"
$lines += "MCP_SELF_URL=$pub"
# Cloudflare 会在边缘写入 CF-Connecting-IP（客户端伪造不了），比 XFF 可靠
$lines += "TRUSTED_IP_HEADER=cf-connecting-ip"
[System.IO.File]::WriteAllLines($envFile, $lines, (New-Object System.Text.UTF8Encoding($false)))
Ok "PUBLIC_BASE_URL / MCP_SELF_URL = $pub，TRUSTED_IP_HEADER=cf-connecting-ip"

# ---------- 5) 重启服务以加载新 .env ----------
Step "重启站点服务"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*uvicorn*' } |
    ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }
Start-Sleep -Seconds 2
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $root -WindowStyle Minimized

$localOk = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 4
        if ($h.status -eq "ok") { $localOk = $true; break }
    } catch {}
}
if (-not $localOk) { Warn "本地服务未就绪，稍后手动检查" } else { Ok "本地服务 OK（已加载 cf-connecting-ip 信任头）" }

# ---------- 6) 替换所有文档/脚本里的旧地址 ----------
Step "替换仓库里的旧公网地址"
$old = "https://pork-capricorn-gulp.ngrok-free.dev"
$targets = @(
    "README.md", "docs\distribution.md", "docs\hf-dataset-card.md", "dataset\README.md",
    "dataset\public-export.json", "tools\refresh_dataset.ps1", ".env.example"
)
$changed = 0
foreach ($t in $targets) {
    $full = Join-Path $root $t
    if (-not (Test-Path $full)) { continue }
    $text = [System.IO.File]::ReadAllText($full, [System.Text.Encoding]::UTF8)
    if ($text -notmatch [regex]::Escape($old)) { continue }
    $new = $text.Replace($old, $pub)
    [System.IO.File]::WriteAllText($full, $new, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "    ✔ $t"
    $changed++
}
Ok "共更新 $changed 个文件"

# ---------- 7) 公网验证（DNS Active 后才有意义） ----------
Step "公网连通性检查"
$ok = $false
for ($i = 0; $i -lt 6; $i++) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing "$pub/health" -UserAgent "cutover-check/1.0" -TimeoutSec 15
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
    Start-Sleep -Seconds 5
}
if ($ok) {
    Ok "$pub/health -> 200"
} else {
    Warn "$pub 暂不可达 —— 通常是因为域名还在 client hold，或 Cloudflare 里 NS 尚未生效（显示 Pending/Active 前属正常）"
}

Write-Host ""
Write-Host "===== 切换完成 =====" -ForegroundColor Green
Write-Host "  公网地址: $pub"
Write-Host "  本地服务: http://127.0.0.1:8000/"
Write-Host "  隧道进程: cloudflared $(if ((Get-Process cloudflared -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) {'运行中'} else {'未运行'})"
Write-Host ""
Write-Host "下一步："
Write-Host "  1. 在阿里云把 NS 改为 Cloudflare 的两条（Cloudflare 显示 Active 后域名才会生效）"
Write-Host "  2. DNS 生效后运行验证：python tools\visitors.py --limit 5"
Write-Host "  3. 把 README/数据集的变更推到 GitHub（git push 或 gh api）"
