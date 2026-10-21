# 把本地运行数据迁移到 VPS（在 Windows 上执行）
#
# 用法：
#   powershell -File deploy/migrate.ps1 -Host 140.238.x.x -User ubuntu -Key C:\Users\asus\.ssh\oci_key
#
# 做三件事：
#   1. 打包 .env 与 data/（数据库、GeoIP 库、隧道令牌）
#   2. scp 上传到服务器 ~/agent-deaddrop/
#   3. 提示在服务器上执行 bootstrap.sh
param(
    [Parameter(Mandatory = $true)][string]$ServerHost,
    [string]$User = "ubuntu",
    [Parameter(Mandatory = $true)][string]$Key,
    [string]$RemoteDir = "agent-deaddrop"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== 1. 检查本地文件 =="
$need = @(".env", "data\messages.db", "data\cloudflared-token.txt")
foreach ($f in $need) {
    if (-not (Test-Path $f)) { throw "缺少 $f（先在本地把服务跑起来一次）" }
    Write-Host "  ✓ $f"
}
$mmdb = Get-ChildItem data -Filter "*.mmdb" -ErrorAction SilentlyContinue
Write-Host "  GeoIP 库: $($mmdb.Count) 个"

Write-Host "== 2. 打包 =="
$bundle = Join-Path $env:TEMP "deaddrop-migrate.tar.gz"
if (Test-Path $bundle) { Remove-Item $bundle -Force }
# 全部用相对路径（解包到服务器时不会写到根目录去）
$files = @(".env", "data/messages.db", "data/cloudflared-token.txt")
$files += Get-ChildItem data -Filter "*.mmdb" -ErrorAction SilentlyContinue | ForEach-Object { "data/" + $_.Name }
$tarArgs = @("-czf", $bundle) + $files
& tar @tarArgs
if ($LASTEXITCODE -ne 0) { throw "打包失败" }
Write-Host "  已打包: $bundle ($([math]::Round((Get-Item $bundle).Length/1KB,1)) KB)"

Write-Host "== 3. 上传 =="
$target = "$User@$($ServerHost)"
& scp -i $Key $bundle "$($target):~/"
if ($LASTEXITCODE -ne 0) { throw "scp 失败（检查 IP / 用户名 / 私钥路径）" }
Write-Host "  已上传到 ~/deaddrop-migrate.tar.gz"

Write-Host "== 4. 服务器端解包 =="
$remote = "mkdir -p $RemoteDir/data && tar -xzf ~/deaddrop-migrate.tar.gz -C $RemoteDir && ls -la $RemoteDir/data"
& ssh -i $Key $target $remote
if ($LASTEXITCODE -ne 0) { throw "远程解包失败" }

Write-Host ""
Write-Host "✅ 数据已就位。接下来："
Write-Host "   ssh -i $Key $target"
Write-Host "   cd $RemoteDir && bash deploy/bootstrap.sh"
Write-Host ""
Write-Host "注意：服务器上的 cloudflared 连上同一个隧道后，会与家里的连接同时存在；"
Write-Host "      确认公网正常后，再回家里的电脑停掉 cloudflared。"
