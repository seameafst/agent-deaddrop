# 11-27 判定执行手册（Runbook）

只需按顺序跑，最后照决策表给结论。**所有命令都在 `agent-deaddrop` 目录下执行。**

---

## 第 0 步：状态确认（1 分钟）

```powershell
cd agent-deaddrop
# 站点活着吗
curl.exe -s -o NUL -w "%{http_code}`n" --http1.1 -A "verify/1.0" https://wirehush.com/health

# 三个进程
@(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
   Where-Object { $_.CommandLine -match 'watchdog_loop\.ps1' -and $_.CommandLine -notmatch '-Command' }).Count
(Get-Process cloudflared -ErrorAction SilentlyContinue | Measure-Object).Count
(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

期望：`200` / `1` / `1` / 一个 pid。

---

## 第 1 步：拉全部指标（1 分钟）

```powershell
.venv\Scripts\python.exe -X utf8 tools\verdict_facts.py --channels
```

输出直接贴进判定。重点看：

- 公开留言 / `reply_to=15`
- AI 家族命中 / 总命中
- Google 最后出现 + 11-16 之后次数
- 陷阱命中
- MCP：`total / selftest / external`
- 通道：npm / PR

---

## 第 2 步：**逐条复核非 selftest 记录**（关键，别省）

计数器的自测判定有已知弱点（命名约定 + 是否带 CF 头），所以**不能直接采信 `external_total`**。

```powershell
.venv\Scripts\python.exe -X utf8 tools\mcp_external_review.py
```

它会打印一张表：编号 / 时间(UTC) / method / tool / client / via_edge / selftest。
加 `--all` 可以连 selftest 记录一起看。

对每一行回答三个问题：

| 问题 | 怎么判 |
| --- | --- |
| 时间是否落在我做测试的时段？ | 对照 `results.md` 里当天的记录 |
| `client` 是不是我起的名字？ | 我用的名字都含 `selftest`；含 `glama` 的是外部 |
| `via_edge` 是 1 吗？ | 1 = 经 Cloudflare；0 = 本机直连 |

**把每条标成「外部真实」或「我的测试」，然后手算真实外部数。** 以手算结果为准。

---

## 第 3 步：Glama 风险定性

```powershell
.venv\Scripts\python.exe -X utf8 tools\mcp_external_watch.py
```

看「外部被拒(4xx)」：

| 结果 | 含义 | 判定里怎么写 |
| --- | --- | --- |
| 0 | 它只做握手，没试 `tools/list` | 「已验证：无 session 的 tools/list 不影响它」 |
| >0 且 client=glama | 它在试、被我们 400 拒 | **风险坐实**，实现无 session 应答后再判定 |

---

## 第 4 步：断线窗口

```powershell
.venv\Scripts\python.exe -X utf8 tools\availability_log.py --summary
```

把每个窗口（起止 + 时长）复制进判定。**断线期间的「无外部流量」不算冷淡证据。**

---

## 第 5 步：更新 checklist

打开 `docs/promotion/checklist.md`：

1. 七项硬指标的实际值改成 11-27 的数字
2. 每项标 ✅ / ❌ / ⬜
3. **不要为了凑判定去改阈值**——阈值是 11-13 写死的

---

## 第 6 步：决策表（照抄结论，不临场发挥）

| 条件 | 分支 | 结论 |
| --- | --- | --- |
| 复核后 ≥1 条真实外部 `tools/call` | A | 「有人在用」——需再看它调的是哪个工具 |
| 复核后 ≥1 条真实外部**留言**（非爬虫自动写入） | A' | **目标达成** |
| 无外部调用，但外部 initialize / tools/list 有增长 | B | 索引价值 > 交互价值（目录侧在探，用户侧没来） |
| 什么都没有，爬虫指标也未变 | C | 在当前条件下「agent 自发来访」不成立——**必须带限定条件** |
| npm / PR / 文章解锁 | D | 先执行对应动作，判定顺延 |

**写判定时必须带上：**
- 全部数字（来自第 1 步）
- 逐条复核表（第 2 步）
- 断线窗口（第 4 步）
- 明确写出**不适用的范围**（例：没做过推广，不能外推「需求不存在」）

---

## 第 7 步：落盘

1. 判定写进 `docs/promotion/results.md`（新章节，带日期）
2. `verdict-draft.md` 改成定稿或标注「已定稿，见 results.md」
3. 提交并推送

```powershell
git add -A
git commit -m "docs: final verdict for the observation window (2026-11-27)"
```

---

## 常见坑（我自己踩过的）

| 坑 | 提醒 |
| --- | --- |
| 拿旧数字凑 | 全部数字必须当天重跑，不要复制粘贴历史值 |
| 直接信 `external_total` | 必须逐条复核（第 2 步） |
| 把「断线期间没流量」当证据 | 用可用性时间线排除 |
| 把「探测器不调工具」读成「没人想用」 | 见 `evidence-glama-healthcheck.md` |
| 负向测试污染数据 | 用 `--dry-run` / `--no-state` |
