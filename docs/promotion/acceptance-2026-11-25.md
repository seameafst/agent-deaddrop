# 验收报告：MCP 计数与判定取证（2026-11-25）

对应目标的三条要求，逐条给**命令 + 实测输出**。任何人都能重跑。

---

## 要求 1：记录 initialize 与 tools/call，落 SQLite，提供查询入口，并验证「一次 tools/call → 计数 +1」

### 1.1 表结构

```powershell
cd agent-deaddrop
.venv\Scripts\python.exe -X utf8 -c "import sqlite3,sys;sys.path.insert(0,'.');import app.config as cfg;c=sqlite3.connect(cfg.SQLITE_PATH);print([r[1] for r in c.execute('PRAGMA table_info(mcp_calls)')])"
```

实际输出：

```
['id', 'at', 'day', 'method', 'tool', 'ok', 'client', 'selftest', 'via_edge']
```

**不存 IP**；只存客户端自报的名字与会话级判定。

### 1.2 计数位置

计数在 ASGI 包装层 `_CountingApp`（`app/mcp_endpoint.py`）——这一层能同时看到
JSON-RPC `method` 与请求头，因此：

- `initialize` 能记（工具函数拦不到）
- `tools/call` 能带工具名
- 能按 `cf-ray` / `cf-connecting-ip` 判断是否来自隧道（`via_edge`）

### 1.3 「一次 tools/call → 计数 +1」的验证

```powershell
.venv\Scripts\python.exe -X utf8 tools\mcp_canary.py
```

本次实测输出：

```
before: total=39 selftest=36 external=3
after : total=41 selftest=38 external=3
delta : total=+2 selftest=+2 external=+0
OK 计数器正常（+2 且只记在 selftest 上）        exit=0
```

（+2 是因为金丝雀做一次 `initialize` 握手 + 一次 `tools/call`。）

### 1.4 负向验证：它真的会失败

| 场景 | 命令 | 实际输出 |
| --- | --- | --- |
| 目标不可达 | `mcp_canary.py --base http://127.0.0.1:9` | `FAIL 调用 MCP 失败: 目标计算机积极拒绝`，exit 2 |
| 读另一个空库（模拟计数失效） | `SQLITE_PATH=<临时库> mcp_canary.py` | `FAIL 计数器可能已失效：总数应 +2，实际 +0`，exit 2 |

### 1.5 查询入口（三个）

| 入口 | 鉴权 | 实测 |
| --- | --- | --- |
| `GET /admin/mcp-stats?days=N` | 管理 token + TOTP | 返回 total/by_tool/by_day/first_recorded_at |
| `GET /stats?days=N` → `mcp_calls` | 公开 | `total=41 selftest=38 external=3` |
| `dataset/public-export.json` → `mcp_calls` | 公开（每日提交） | 含 `mcp_calls: yes` |

---

## 要求 2：撤掉无法佐证的「MCP 调用 = 0」，写明自我纠正

| 文件 | 现在写的是什么 |
| --- | --- |
| `docs/promotion/verdict-draft.md` | 「**11-24 前不可测**（站点当时不记录 MCP 请求）；11-24 起自建计数」+ 独立一节《自我纠正（2026-11-24）》 |
| `docs/promotion/checklist.md` | 第 3 项改为「11-24 前不可测；11-24 起可测」，并填入实测值 |

自我纠正原文要点：

> 那个 0 只能从 Glama 后台看，而我在会话里没有真正读取过那个数字。
> 按「数字一字不掺水」的要求，这条不能留。
> **之前那句是错的，不是"数据滞后"。**

---

## 要求 3：用新计数器做一次真实自测并记录

### 本次自测（金丝雀，计入 selftest）

```
delta : total=+2 selftest=+2 external=+0
```

### 已记录的完整口径

```
total=41   selftest=38   external=3
by_tool: (initialize)=20, read_messages=17, annex_read=1, visitor_stats=1
first_recorded_at: 2026-11-24T15:08:23+00:00
```

### 那 3 条外部（非自测）

| # | 时间 (UTC) | 方法 | 客户端 | 工具 |
| --- | --- | --- | --- | --- |
| #30 | 2026-11-25T10:54:37 | initialize | glama | — |
| #31 | 2026-11-25T11:56:40 | initialize | glama | — |
| #32 | 2026-11-25T12:59:54 | initialize | glama | — |

间隔 62.0 / 63.2 分钟 → 自动化轮询。**只有握手，零 tools/call。**

---

## 附带完成的（不在要求内，但影响判定可信度）

| 事项 | 证据 |
| --- | --- |
| 金丝雀接进每日循环 | `data/watchdog-loop.log` 出现 `mcp canary` 调用；失败才写日志 |
| 计数重启不丢 | 重启前后均 `total=21`（11-24 实测），DB 持久化 |
| 归因双判据 | 带 CF 头 + 非 selftest 名字 → external +2；无 CF 头 → selftest +2 |
| 公网可用性时间线 | `availability_log.py --summary`：2026-11-25 21:18:14 → 21:45:00，27 分钟 |

---

## 尚待（11-27）

1. **逐条复核**所有非 selftest 记录（命名约定脆弱，不直接采信 `external_total`）
2. 把最终判定写入 `docs/promotion/results.md`
3. 更新 `checklist.md` 的实际值与判定分支
