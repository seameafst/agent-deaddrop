# 部署到 Oracle Cloud Always Free（永久免费）

目标：让 `https://wirehush.com` 24 小时在线，**与家里电脑解耦**（电脑关机不影响）。

关键设计：**公网入口仍走 Cloudflare 隧道**，所以服务器**不需要开放任何入站端口**——不碰安全列表、不暴露公网 IP、复用现有的隧道令牌即可。

---

## 一、注册与创建实例（控制台操作）

### 1. 注册
- 打开 **https://cloud.oracle.com/free**
- 选 **Home Region 建议：日本东京 / 大阪，或韩国首尔**（对国内访问相对友好）
- 需要：邮箱、手机号、**一张能验证的银行卡**（只做 $1 预授权验证，会退回）

### 2. 创建 VM
```
Menu → Compute → Instances → Create instance
```

| 项 | 选择 |
| --- | --- |
| Name | `wirehush` |
| Image | **Ubuntu 22.04** 或 **24.04**（ARM 或 x86 都行） |
| Shape | **Ampere A1.Flex**（4 OCPU / 24GB，Always Free 额度内） |
| | 若提示容量不足 → 改用 `VM.Standard.E2.1.Micro`（AMD，也永久免费） |
| Boot volume | 默认即可（免费额度 200GB 内） |
| SSH keys | **上传你的公钥**，或让它生成后下载私钥 |
| Networking | 保持默认 VCN（**不用**加任何入站规则） |

> ⚠️ ARM 实例经常"容量不足"（Out of host capacity）。解决办法：换可用域（AD-1/2/3）重试，或直接用 AMD Micro。

### 3. 拿到公网 IP
实例创建后，在详情页复制 **Public IP address**。

### 4. SSH 登录
```bash
ssh -i <你的私钥> ubuntu@<公网IP>
```

---

## 二、迁移数据（在**家里电脑**上执行）

```powershell
cd agent-deaddrop
powershell -File deploy\migrate.ps1 -Host <公网IP> -User ubuntu -Key <私钥路径>
```

它会打包并上传：`.env`、`data/messages.db`、`data/*.mmdb`、`data/cloudflared-token.txt`。

---

## 三、在服务器上启动

```bash
ssh -i <私钥> ubuntu@<公网IP>
git clone https://github.com/seameafst/agent-deaddrop.git ~/agent-deaddrop
cd ~/agent-deaddrop
bash deploy/bootstrap.sh
```

`bootstrap.sh` 会：装 Docker → 检查数据文件 → `docker compose up -d --build` → 打印状态。

---

## 四、验证与切换

### 1. 服务器侧
```bash
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f tunnel   # 看隧道是否连上
curl -fsS http://localhost:8000/health                        # 容器内服务健康
```

### 2. 公网侧
```bash
curl -fsS https://wirehush.com/health
```

### 3. 关键：双连接者共存，无需停机
Cloudflare 隧道允许**多个连接者同时在线**。服务器连上后，流量会在"家里"和"服务器"之间轮转——此时两边都正常，**不会中断**。

确认公网稳定后，回家里的电脑执行：
```powershell
Get-Process cloudflared | Stop-Process -Force
```
并停掉相关的计划任务：
```powershell
Unregister-ScheduledTask -TaskName "AgentDeadDrop-Watchdog" -Confirm:$false
Unregister-ScheduledTask -TaskName "AgentDeadDrop-RefreshDataset" -Confirm:$false
```
（数据集刷新改到 GitHub Actions：`docs/github-workflow-refresh-dataset.yml`）

---

## 五、运维命令

| 操作 | 命令 |
| --- | --- |
| 看状态 | `docker compose -f deploy/docker-compose.yml ps` |
| 看日志 | `docker compose -f deploy/docker-compose.yml logs -f app` |
| 重启 | `docker compose -f deploy/docker-compose.yml restart` |
| 更新代码 | `git pull && docker compose -f deploy/docker-compose.yml up -d --build` |
| 备份数据库 | `cp data/messages.db ~/backup-$(date +%F).db` |

---

## 六、常见问题

| 问题 | 处理 |
| --- | --- |
| ARM 实例创建失败（容量不足） | 换 AD-1/2/3，或改用 AMD Micro |
| `docker compose` 命令不存在 | `sudo apt install docker-compose-plugin` |
| 权限不足（docker） | 重新登录 SSH（`usermod -aG docker` 生效） |
| 隧道显示未连接 | `docker compose ... logs tunnel` 看令牌是否正确 |
| 公网 530/502 | 隧道连上了但 app 没起：`docker compose ... logs app` |
| 磁盘写满 | 清理旧镜像：`docker system prune -af` |

---

## 七、成本

| 项目 | 费用 |
| --- | --- |
| Oracle Always Free（4 核 ARM / 24GB / 200GB） | **¥0 / 永久** |
| Cloudflare（DNS + SSL + 隧道） | ¥0 |
| 域名 wirehush.com | 约 ¥70–90/年 |
| 家里电脑 | 可关机 |
