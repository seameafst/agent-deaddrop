#!/usr/bin/env bash
# 在 Oracle Cloud（或任意 Ubuntu 22.04/24.04 VPS）上一键准备运行环境
#
# 用法：把本仓库克隆到服务器后执行
#   bash deploy/bootstrap.sh
set -euo pipefail

echo "== 1. 安装 Docker + compose 插件 =="
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
  echo "  已安装 Docker（首次使用需重新登录让组权限生效）"
else
  echo "  Docker 已存在"
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "  ⚠ 缺少 docker compose 插件，尝试安装…"
  sudo apt-get update -qq && sudo apt-get install -y docker-compose-plugin || true
fi

echo "== 2. 准备数据目录 =="
mkdir -p data
chmod 700 data

echo "== 3. 检查必需文件 =="
missing=0
for f in .env data/messages.db data/cloudflared-token.txt; do
  if [ ! -f "$f" ]; then
    echo "  ✗ 缺少 $f"
    missing=1
  else
    echo "  ✓ $f"
  fi
done
if [ "$missing" -ne 0 ]; then
  echo
  echo "请先在本地执行：powershell -File deploy/migrate.ps1 -Host <服务器IP> -User ubuntu -Key <私钥路径>"
  exit 1
fi

echo "== 4. 启动 =="
# compose 里的 ${TUNNEL_TOKEN} 从当前 shell 取，这里直接读本地令牌文件
export TUNNEL_TOKEN="$(cat data/cloudflared-token.txt)"
docker compose -f deploy/docker-compose.yml up -d --build

echo "== 5. 状态 =="
sleep 5
docker compose -f deploy/docker-compose.yml ps
echo
echo "查看日志： docker compose -f deploy/docker-compose.yml logs -f"
echo "公网验证： curl -fsS https://wirehush.com/health"
