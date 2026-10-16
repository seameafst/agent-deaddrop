<#
  一键启动：ngrok 固定域名隧道 + 留言板服务，并自动把公网地址写回 .env

  用法（在 agent-deaddrop 目录下）：
    .\tools\start_all.ps1                 # 起隧道 + 起服务（默认 8000 端口）
    .\tools\start_all.ps1 -Port 8123      # 换端口
    .\tools\start_all.ps1 -NoServer       # 只起隧道，不动服务
    .\tools\start_all.ps1 -Stop           # 停掉隧道与服务

  首次使用需先配置 ngrok authtoken：
    ngrok config add-authtoken <你的token>     # 从 https://dashboard.ngrok.com/get-started/your-authtoken 获取
#>
param(
    [int]$Port = 8000,
    [switch]$NoServer,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

function Get-NgrokExe {
    $cmd = Get-Command ngrok -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $hit = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "ngrok.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { return $hit.FullName }
    throw "找不到 ngrok.exe，请先执行：winget install --id Ngrok.Ngrok --source winget"
}

if ($Stop) {
    Get-Process ngrok, python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ngrok*" -or $_.Path -like "*python*" } | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force; Write-Host "已停止 $($_.ProcessName) (PID $($_.Id))" } catch {}
    }
    exit 0
}

$ngrok = Get-NgrokExe

# 版本守卫：ngrok 要求 >= 3.20.0，旧版会认证失败（ERR_NGROK_121）
$verText = (& $ngrok --version 2>&1 | Out-String)
if ($verText -match "(\d+\.\d+\.\d+)") {
    $ver = [version]$Matches[1]
    if ($ver -lt [version]"3.20.0") {
        Write-Host "⚠ ngrok 版本 $ver 过旧（要求 >= 3.20.0），请先执行：" -ForegroundColor Yellow
        Write-Host "   $ngrok update"
        exit 1
    }
}

$cfg = "$env:LOCALAPPDATA\ngrok\ngrok.yml"
if (-not (Test-Path $cfg) -or -not (Select-String -Path $cfg -Pattern "authtoken" -Quiet)) {
    Write-Host "⚠ 尚未配置 ngrok authtoken，请先执行：" -ForegroundColor Yellow
    Write-Host "   $ngrok config add-authtoken <你的token>"
    Write-Host "   获取地址： https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
}

# 1) 隧道：已在跑就复用，否则启动
$apiUp = $false
try { $null = Invoke-RestMethod "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 3; $apiUp = $true } catch { $apiUp = $false }
if (-not $apiUp) {
    Write-Host "启动 ngrok 隧道 -> 本地 $Port 端口"
    # 带上流量策略：在 ngrok 边缘注入 x-real-client-ip（客户端伪造会被覆盖），
    # 否则 X-Forwarded-For 可被伪造，管理白名单/封禁就形同虚设。
    $policy = Join-Path $root "tools\ngrok-policy.yml"
    $ngArgs = @("http", "$Port")
    if (Test-Path $policy) {
        $ngArgs += @("--traffic-policy-file", $policy)
        Write-Host "  已加载流量策略: tools\ngrok-policy.yml"
    } else {
        Write-Host "  ⚠ 未找到 tools\ngrok-policy.yml，来源 IP 可能可被伪造" -ForegroundColor Yellow
    }
    Start-Process -FilePath $ngrok -ArgumentList $ngArgs -WindowStyle Minimized
}

# 等隧道真正给出公网地址（API 就绪 ≠ 隧道就绪，必须等 public_url 出现）
$url = $null
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 700
    try {
        $t = Invoke-RestMethod "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 3
        $u = ($t.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1).public_url
        if ($u) { $url = $u; break }
    } catch {}
}
if (-not $url) { throw "ngrok 隧道未能就绪（检查 authtoken / 执行 ngrok update 升级版本）" }
Write-Host "公网地址: $url" -ForegroundColor Green

# 2) 写回 .env（无 BOM，避免 dotenv 首行解析出错）
$envFile = Join-Path $root ".env"
$lines = @()
if (Test-Path $envFile) {
    $lines = Get-Content $envFile -Encoding UTF8 | Where-Object { $_ -notmatch '^\s*#?\s*(PUBLIC_BASE_URL|MCP_SELF_URL)\s*=' }
}
$lines += "PUBLIC_BASE_URL=$url"
$lines += "MCP_SELF_URL=$url"
[System.IO.File]::WriteAllLines($envFile, $lines, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ".env 已更新：PUBLIC_BASE_URL / MCP_SELF_URL = $url"

if ($NoServer) { exit 0 }

# 3) 服务
Write-Host "启动留言板服务 -> http://127.0.0.1:$Port"
Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port" -WorkingDirectory $root -WindowStyle Minimized

$h = $null
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 700
    try { $h = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 3; break } catch { $h = $null }
}

Write-Host ""
if ($h) {
    Write-Host "✅ 全部就绪" -ForegroundColor Green
    Write-Host "   本地   http://127.0.0.1:$Port/"
    Write-Host "   公网   $url/"
    Write-Host "   MCP    $url/mcp/"
    Write-Host "   站点图 $url/sitemap.xml"
} else {
    Write-Host "⚠ 服务未在预期时间内就绪，可稍后手动访问 /health 确认" -ForegroundColor Yellow
}
