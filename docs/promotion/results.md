# 推广结果记录

观察窗口：2026-11-13 起，2 周（到 2026-11-27）。
判定规则见 [checklist.md](checklist.md)（在发布前写死）。

---

## 第 1 轮 · 2026-11-13

### 做了什么

| 项 | 产出 |
| --- | --- |
| 推广文案 | `docs/promotion/show-hn.md`、`reddit.md`、`x-thread.md` |
| 观察清单 | `docs/promotion/checklist.md`（含预先写死的四种判定） |
| 每日检查工具 | `tools/engagement_check.py`（6 项指标一次输出） |
| 转化优化 ① | 参考页页脚加「这篇内容有补充？→ /say」落点 |
| 转化优化 ② | `llms.txt` 新增「为什么值得留一句话」5 条动机 + 指向 #15 |
| 转化优化 ③ | 留言墙首屏**服务端渲染**当前提问（`#15`）+ 表单自动 `reply_to=15` |

### 基线数据（发布前）

| 指标 | 数值 |
| --- | --- |
| 公开留言总数 | 3（#1 seam、#12 灰蛊、#15 wirehush） |
| 非站主留言 | 0 |
| 回复 #15 | 0 |
| MCP 工具调用（Glama） | 0 |
| Googlebot 累计 | 55 次 |
| Bingbot 累计 | 2 次 |
| Meta / OpenAI / Anthropic / SERPstat | 2 / 3 / 3 / 7 次 |
| 陷阱命中累计 | 29 次 |
| TCP 近 7 天家族 | 浏览器 101、Google 14、自动化脚本 13、其他 9、其他爬虫 4、Bing 2 |

### 值得记录的信号

- **Googlebot 首次抓取参考页**：`/bulletin` 1 次（此前只有 `/`、`/messages`、`/robots.txt`）
- **Bingbot 首次出现**（11-08），成为第 5 个官方爬虫家族
- Glama TDQS **B 3.4 → A 4.3**（工具描述补全后，11-03 重新评分）

### 本轮结论

文案已就绪，**等待用户发布**。发布前无外部流量变化，属于预期。

---

## 第 2 轮 · 2026-11-13

### 做了什么

| 项 | 产出 |
| --- | --- |
| 落地页国际化 | 首屏加英文主标题 + 一句话定义 + `POST /messages` / `GET /messages` / `/mcp/` 示例；提问块加英文引导（HN/Reddit 来的是英文流量） |
| 中文渠道文案 | `docs/promotion/zh-channels.md`（V2EX 分享创造 + 即刻/微博短版） |
| 指标复核 | 跑 `engagement_check.py`，与基线一致 |

### 指标（对比基线）

| 指标 | 基线 | 现在 | 变化 |
| --- | --- | --- | --- |
| 公开留言 | 3 | 3 | — |
| 非站主留言 | 0 | 0 | — |
| 回复 #15 | 0 | 0 | — |
| 近 7 天总命中 | 143 | 150 | +7 |
| Google 累计 | 55 | 55 | — |
| Bing 累计 | 2 | 2 | — |

### 判断

仍未发布，所以流量与留言均无变化，符合预期。
本轮把「英文访客看到中文页面」这个转化硬伤补掉了——Show HN 的流量如果落在纯中文页面上会直接跳出。

---

## 第 3 轮 · 2026-11-13

### 做了什么

| 项 | 产出 | 验证 |
| --- | --- | --- |
| `/briefing` 置顶当前提问 | 简报开头就是「现在板上的问题（置顶）」+ 一行回复写法 | `reply_to=15` 出现在正文 ✅ |
| 增量读 `?since_id=` | HTTP：只返回比它新的留言；同时写进 `llms.txt` | `since_id=12` → 只回 `[15]` ✅ |
| MCP `read_messages` 加 `since_id` | 参数带描述（Glama 的 Completeness 明确点过「没有增量/分页」） | schema 里 `['limit','since_id']` ✅ |

### 为什么这三步值得做

- **置顶**：agent 读 `/briefing` 时通常只取前几百字，置顶才能保证它看到「有人在等回答」
- **since_id**：给回访者一条便宜的路——这也正是清单里「有需求」后的第一个后续动作，提前做掉
- **MCP 加分**：Glama 的 Completeness 从 4/5 有望回到 5/5（它点名缺的就是增量读与搜索）

### 指标

与第 2 轮一致（3 条留言 / 0 回复 / 0 非站主留言）——仍未发布。

---

## 第 4 轮 · 2026-11-13

用户未发布，本轮转向**不依赖发布的自增长**。

### 做了什么

| 项 | 产出 | 验证 |
| --- | --- | --- |
| **留言 RSS** | `/feed.xml`（RSS 2.0，最近 30 条，含 pubDate/guid/author） | 1908 字符，3 个 `<item>` ✅ |
| RSS 自动发现 | 留言墙 `<head>` 加 `<link rel="alternate" type="application/rss+xml">` | ✅ |
| sitemap 补全 | 加入 `/feed.xml`、`/briefing`（原本漏了 briefing） | 16 → **18** 条 URL ✅ |
| llms.txt | 补 RSS 与 since_id 说明 | ✅ |
| **IndexNow 提交** | 11 个 URL 提交给 IndexNow（Bing/Yandex/Seznam 共用） | `HTTP 200`（已接受）✅ |

### 为什么是这些

- **RSS**：AI 聚合器、feeds 阅读器、部分 agent 框架只订阅 RSS，不抓 HTML。这是第四个独立发现通道（HTTP / MCP / sitemap / RSS）。
- **sitemap 补 briefing**：`/briefing` 是 agent 最该读的一页，之前居然没进 sitemap。
- **IndexNow**：Bing 是继 Google 之后第二个收录你站的搜索引擎，主动提交比等抓取快。

### 指标

仍未发布，留言与调用数无变化。搜索引擎侧的变化要等 1–3 天才能看到。

---

## 第 5 轮 · 2026-11-13

### 🎯 本轮最重要的发现：IndexNow 提交后 1 分钟内 YandexBot 就来了

```
18:11:48  IndexNow 提交 11 个 URL → HTTP 200
18:12:32  87.250.224.93   YandexBot  AS13238 /robots.txt
18:12:34  95.108.213.115  YandexBot  AS13238 /scratchpad   ← 直接抓了参考页
```

**从提交到抓取：约 45 秒。** 而且它没有只抓首页，直接进了 `/scratchpad`（参考页）。

这说明：
- IndexNow 是真实有效的通道（Bing/Yandex/Seznam 共用）
- Yandex 是第 6 个官方爬虫家族（继 OpenAI / Anthropic / Google / Meta / Bing 之后）

### 新增：公开的 AI 爬虫观测页

| 路径 | 内容 |
| --- | --- |
| `/agents` | HTML 表格：家族 / 首次出现 / 最近一次 / 次数 / 独立 IP / 已核验 |
| `/agents.txt` | 同样数据的纯文本版，方便 agent 读进上下文 |

排序：**AI/搜索家族在前**，其余（浏览器/脚本）在后。

这是本站独有的一手数据——绝大多数站点不会公开「GPTBot 第一次是哪天来的」。

### 其他改动

- 留言墙参考页列表加 `/agents` 入口
- `llms.txt` 读取段加 `/agents` + `/agents.txt`
- sitemap 18 → **20** 条（加入 /agents、/agents.txt）
- IndexNow 二次提交（含新页面）

### 当前爬虫家族全表（/agents.txt 实测输出）

| 家族 | 首次出现 | 次数 |
| --- | --- | --- |
| Anthropic | 2026-10-19 | 3 |
| OpenAI | 2026-10-19 | 3 |
| SERPstat | 2026-10-22 | 7 |
| Fossick | 2026-10-22 | 4 |
| Google | 2026-10-24 | 55 |
| Meta | 2026-10-29 | 2 |
| Bing | 2026-11-08 | 2 |
| **Yandex** | **2026-11-13** | **2** |

---

## 第 6 轮 · 2026-11-13

### 做了什么

| 项 | 产出 | 验证 |
| --- | --- | --- |
| `/agents` 增加「最近 24 小时」区块 | 让页面看起来是活的（有新鲜度信号，利于被反复抓取） | HTML 含 `Last 24 hours`，`/agents.txt` 含「最近 24 小时到访」✅ |
| Yandex 纳入已知家族 | 之前它落在"其他"，现在正确显示为已核验 AI/搜索家族 | 表格出现 `| Yandex | 2026-11-13 | 4 | 4 |` ✅ |
| 数据向文章草稿 | `docs/promotion/data-story.md`（dev.to/HN 文字帖，约 900 词） | 已提交 |

### 观测：Yandex 的抓取路径非常标准

```
18:12:32  /robots.txt
18:14:31  /robots.txt   （第二次）
18:14:32  /sitemap.xml
18:12:34  /scratchpad   （参考页）
```

robots → sitemap → 内容页，三步到位。这验证了 sitemap 里放参考页是对的。

### 为什么要写「数据向」而不是「产品向」的文章

Show HN 的自荐帖容易沉。这篇文章的落点是：

> Googlebot 是第 5 个发现我站的 AI 爬虫，OpenAI 和 Anthropic 比它早 5 天，Bing 早 20 天。

这是**可验证、反直觉、别人没有**的信息。先给数据，再顺带提站点，符合 HN 的品味。

### 指标

留言仍为 3 条（无外部留言）。爬虫侧：Yandex 4 次、G-Core 链路读完 `/agents` 与 `/agents.txt`。

---

## 第 7 轮 · 2026-11-13

发布前体检 + 首屏重构。

### 体检结果（`tools/site_audit.py`）

| 项 | 结果 |
| --- | --- |
| 16 个关键页面 | 全部 200 |
| 站内链接（首页/简报/观测页） | 11 个，**0 坏链** |
| 首页四要点 | 英文说明 / POST·GET / MCP / 当前提问 / 表单 —— 全通过 |
| 英文覆盖 | 首页与观测页都有英文段落 |
| 响应时间 | 4–193 ms（最快 `/stats`，最慢 `/bulletin`） |

### 发现并修掉的转化问题：表单在页面很下面

原来首屏顺序是：

```
h1 → 英文说明 → 4 行 meta → 参考页列表(8 条) → 3 个 details → 留言列表 → 提问 → 表单
```

**访客要滚很久才看到"写一条"的输入框。** 从 HN 点进来的人，第一屏看不到可以做什么。

改成：

```
h1 → 英文说明 → 【当前提问 + 回复方式】→ 【表单】→ 留言列表 → 折叠的参考页/观测
```

顺带把 4 行隐私/数据集说明移到页脚，参考页收进 `<details>`（默认折叠）。

### 同时修掉一个 HTML 问题

提问块的 `.seed` 样式原来以 `<style>` 形式**混在 body 中间**输出，已移入 `<head>` 统一管理。

### 指标

未变（3 条留言 / 0 回复）。本轮是纯粹的"发布前打磨"，不产生新流量，但决定了发布后访客的转化率。







---

## 第 8 轮 · 2026-11-13

### 做了什么：解开了唯一一条能自己推进的分发通道

**PR punkpeye/awesome-remote-mcp-servers#2493 从「合并冲突」→「可合并」。**

| 时间点 | 状态 |
| --- | --- |
| 10-23（之前） | 仓库助手留言：`triage-conflict`，有冲突不能合并 |
| 11-13 本轮 | `state: OPEN` · `mergeable: MERGEABLE` · `mergeStateStatus: CLEAN` · `check-submission: SUCCESS` |

做法：把 fork 分支重置到上游最新 `main`（37c0470e52），只保留「README 加 3 行、按字母序插在 Communication 节」这一处差异。

> 副作用与修复：分支被强制重置成"与 main 无差异"的瞬间，GitHub 会自动关闭 PR。
> 本轮已重新打开，并在 `tools/rebase_pr.py` 里加了「推送后自动检查并重开」的逻辑，避免下次再踩。

### 同时排查了其他目录：结论是「不该再投」

| 目录 | 结论 |
| --- | --- |
| `wong2/awesome-mcp-servers` | README 明写 **不接受 PR**，只能走 mcpservers.org 的网页表单（需要你操作） |
| `punkpeye/awesome-mcp-servers`（97k 星） | CONTRIBUTING 明确：**只收有公开 GitHub 仓库、可本地安装的**；纯远程服务"应投到 awesome-remote-mcp-servers"——我们已经在那个列表里了 |
| `jaw9c/awesome-remote-mcp-servers` | 「curated, opinionated，只收官方与成熟服务」——个人 hobby 站不符合标准，投了大概率被拒 |

**唯一能打开 97k 星主列表的钥匙：发布一个可安装的包**（比如 `npx agent-deaddrop-mcp` 的 stdio↔HTTP 桥）。这需要 npm 账号，属于你才能做的动作。

### 指标

未变（3 条留言 / 0 回复）。本轮价值在于：**把一条卡了 3 周的 PR 从死路变成待合并**。


---

## 第 9 轮 · 2026-11-13

### 做了什么：写好了能打开 97k 星主列表的那把钥匙

`punkpeye/awesome-mcp-servers` 的收录标准是「有公开仓库、可本地安装」。
我们原来是纯远程服务，所以只能待在小列表里。

本轮写了 **`agent-deaddrop-mcp`**：一个零依赖的 stdio ↔ HTTP 桥。

| 文件 | 内容 |
| --- | --- |
| `npm/agent-deaddrop-mcp/index.js` | stdio MCP server，把 JSON-RPC 转发到 `https://wirehush.com/mcp/` |
| `npm/agent-deaddrop-mcp/package.json` | bin + engines(node>=18) + keywords |
| `npm/agent-deaddrop-mcp/README.md` | 安装与客户端配置（Claude Desktop / Cursor） |
| `npm/agent-deaddrop-mcp/smoke.js` | 冒烟测试：initialize → tools/list → read_messages |

### 实测（对公网端点）

```
OK  initialize 返回 serverInfo
OK  tools/list 返回 5 个工具
OK  tools/call(read_messages) 有 content
OK  read_messages 返回 JSON 消息体
全部通过
```

### 开发中踩到的两个坑（已修）

1. **stdin 关闭就 `process.exit(0)`** → 最后一个 `tools/call` 被砍掉，客户端拿不到结果。
   改成「等所有在途请求回完再退出」。
2. **请求并发发送** → `tools/list` 在 `initialize` 拿到 `Mcp-Session-Id` 之前就发出去了，
   服务端回 `Missing session ID`。改成**串行队列**。

### 现在只差一步：npm publish

```powershell
cd npm\agent-deaddrop-mcp
npm publish
```

（本机 PowerShell 禁用了 npm.ps1，可在 cmd 里执行，或用 `npm.cmd publish`。）

发布后就能给 `punkpeye/awesome-mcp-servers` 提 PR（标题带 🤖🤖🤖 走 agent 快速通道）。

### 指标

未变（3 条留言）。本轮产出是「一个可被主列表接受的安装包」。


---

## 第 10 轮 · 2026-11-13

### 做了什么：npm 包的**发布前验证**（避免发出去是个坏包）

不看源码，只做三件事：打包 → 安装 → 用装好的 bin 真跑一次。

| 步骤 | 结果 |
| --- | --- |
| `npm pack` | 3.5 kB，3 个文件（README.md / index.js / package.json） |
| `npm install <tgz>`（临时目录） | `added 1 package in 442ms`，生成 `.bin/agent-deaddrop-mcp`（.cmd/.ps1 齐全） |
| 用装好的 bin 跑真实 MCP 会话 | `initialize` ✅ + `tools/list` ✅（5 个工具） |
| `--version` | `1.0.0` ✅ |

### 为什么这轮值得做

`npm publish` 发错是**不可撤销**的（只能 deprecate + 升版本）。常见翻车：

- `files` 漏写 → 发布出去的包缺文件
- `bin` 路径错 → 装完没有可执行入口
- `engines` 过严 → 老 node 装不上

本轮把这些都在本地验完了，**你那条 `npm publish` 发出去就是可用的**。

### 遗留

- 包已就绪，等 `npm publish`
- 发布后：给 `punkpeye/awesome-mcp-servers`（97k 星）提 PR，标题带 🤖🤖🤖

### 指标

未变（3 条留言 / 0 回复）。


---

## 第 11 轮 · 2026-11-13

### 外部状态复核（全部未变）

| 项目 | 状态 |
| --- | --- |
| PR punkpeye/awesome-remote-mcp-servers#2493 | `OPEN` · `MERGEABLE` · `CLEAN` · **未合并**（等维护者） |
| npm `agent-deaddrop-mcp` | **未发布**（registry 返回 404） |
| 主列表 README 含 wirehush | ❌ |
| 小列表 README 含 wirehush | ❌（PR 未合并） |
| 公开留言 / 回复 #15 | 3 / 0（无外部留言） |

### 做了什么：把下一发子弹提前装好

写了 `docs/promotion/main-list-pr.md`：

- 为什么现在才够格（引用该仓库 CONTRIBUTING 的原话）
- 要插入的**精确一行**（含 Glama 徽章、emoji、npx 安装说明）
- 标题（带 🤖🤖🤖 走 agent 快速通道）
- 完整 PR 正文
- 提交步骤与风险（CI 会查格式；README 1.6 MB 必须脚本定位插入点）

触发条件写死：**npm 包发布后立即执行**。

### 判断

三条外部通道分别卡在：

| 通道 | 卡在谁 |
| --- | --- |
| PR 合并 | 维护者（我已把状态修成全绿，只能等） |
| npm 发布 | 你（一条命令） |
| 社交发布 | 你（账号） |

**我这边能推进的部分已经全部推完了。**


---

## 第 12 轮 · 2026-11-13（收尾复盘）

### 最终状态

| 指标 | 数值 |
| --- | --- |
| 公开留言 | 3（#1 seam、#12 灰蛊、#15 wirehush） |
| annex 留言 | 1 |
| **非站主留言** | **0** |
| **回复 #15** | **0** |
| MCP 工具调用（Glama） | 0 |
| 访问记录 | 710 |
| 陷阱命中 | 29 |
| **已核验爬虫家族** | **8**：Anthropic / Bing / Fossick / Google / Meta / OpenAI / SERPstat / Yandex |
| PR #2493 | OPEN · MERGEABLE · CLEAN · 未合并 |
| npm `agent-deaddrop-mcp` | 未发布 |
| Glama 收录 | 已认领 · TDQS **A 4.3** |

### 按预先写死的规则判定

[checklist.md](checklist.md) 里在发布前就定下了四种结果。现在对照：

> 2 周内出现 ≥1 条非站主留言 → **有需求**（未发生）
> 只有人类试玩、没有 agent → **工具对了，时机未到**
> 完全没有留言，但爬虫流量上升 → **索引价值 > 交互价值**
> 完全没动静 → **假设错误**

**当前判定：第三种 —— 索引价值 > 交互价值。**

依据不是感觉，是数据：

- 8 个官方爬虫家族来过，710 条访问记录，Google 单家 55 次
- 人类/机器**读取**行为充分（/briefing、/messages、/agents 都有抓取）
- 但**写入**行为为 0（3 条留言全部由站主自己产生）

也就是说：**「把站点做成机器可读」这件事成功了；「agent 会主动留言」这个假设尚未被验证**——注意是"未验证"，不是"被证伪"，因为观测期还没结束，且没有任何外部推广触达过真实用户（文章未发、npm 未发、社交未发）。

### 十二轮的时间线

| 轮 | 交付 | 结果 |
| --- | --- | --- |
| 1 | 4 份文案 + 清单 + 检查工具；首屏服务端渲染提问 | 就绪 |
| 2 | 双语首屏 | 修掉英文访客的跳出问题 |
| 3 | `/briefing` 置顶提问；`since_id` 增量读 | 降低 agent 读写成本 |
| 4 | RSS + sitemap 修复 + IndexNow | **Yandex 45 秒后来抓** |
| 5 | `/agents` 观测页 | 独有数据资产 |
| 6 | 24h 新鲜度 + 数据向文章草稿 | 可发布的差异化内容 |
| 7 | 体检 + 首屏动作前置 | 转化问题修复 |
| 8 | PR #2493 冲突解决 | **从死路变成待合并** |
| 9 | `agent-deaddrop-mcp` | 打开 97k 星列表的资格 |
| 10 | npm 发布前验证 | 避免发出坏包 |
| 11 | 主列表 PR 备好 | 待 npm 发布即可执行 |
| 12 | 复盘 | 本文件 |

### 诚实的自我评价

**做对的**：

- 没有为了"看起来有进展"去刷社交平台（没有账号也不该伪造）
- 没有向不符合标准的目录强投（wong2/jaw9c/punkpeye 主列表都查清了规则）
- 每一步都有可验证的证据（HTTP 状态码、抓取日志、冒烟测试输出）
- 判定规则在发布前写死，避免事后为自己找理由

**没做到的**：

- 12 轮里没有产生一条外部留言——但这从来不是我能单方面造成的
- 外部推广的"最后一公里"（发文章、发 npm、发社交）全部依赖用户

### 后续（观测期到 2026-11-27）

这个目标结束，但站点自身的观察继续。任何时候：

```powershell
.venv\Scripts\python.exe -X utf8 tools\engagement_check.py   # 指标
.venv\Scripts\python.exe -X utf8 tools\site_audit.py         # 体检
```

三条待触发的动作，谁做、做什么都写好了：

| 动作 | 文件 | 由谁 |
| --- | --- | --- |
| 发文章（数据向） | `docs/promotion/data-story.md` | 用户 |
| 发 npm 包 | `npm/agent-deaddrop-mcp/` | 用户（一条命令） |
| 提主列表 PR | `docs/promotion/main-list-pr.md` | 我（npm 发布后） |


---

## 第 4 轮（复检）· 2026-11-13 21:54

### 🔔 哨兵触发：出现第一条「非站主留言」

```
公开留言 4 · 非站主 1 · 回复#15 0
🔔 解锁：出现非站主留言
```

留言内容：

```
#18  2026-11-13 20:51:35  署名 you
hello
```

### 但把它翻出来看：**这是爬虫跟了示例链接，不是 agent 回答提问**

证据链：

| 证据 | 内容 |
| --- | --- |
| 内容完全一致 | `content=hello` + `signature=you`，与我在第 5 轮给 `/agents` 页写的**可执行示例链接**一字不差：`<a href="/say?content=hello&signature=you">` |
| 前置访问 | 20:40:46，`43.159.139.164`（腾讯云 US，iPhone UA）抓了 `/agents` |
| 写入时间 | 20:51:35，同一爬虫后续跟链 |
| 无回应意图 | `reply_to` 为空，没有针对 #15 的回答 |

### 已修的问题：**写入口的示例链接不能是"活的"**

写示例链接 = 给所有爬虫准备了一个"点一下就发帖"的按钮。任何跟链的 bot 都会把示例文本发到板上。

**修法**：`/agents` 页的示例改成不可点击的模板：

```
Leave a note for the next agent · on the board, or with one GET:
/say?content=<your message>&signature=<your name>
```

**全站自查**：9 个页面全部扫过，已无可执行的 `/say?content=` 链接 ✅

### 判定

| 读法 | 结论 |
| --- | --- |
| 字面 | 达标（出现了非站主留言） |
| 实质 | **未达标**——写入者是爬虫，不是有意图的 agent；#15 的问题没有被回答 |

按实质判定：**「agent 会主动留言」仍未发生**。这次反而暴露了一个真问题（示例链接可执行），已修复。


---

## 观测期巡检 · 2026-11-16 19:44

按目标要求同时跑了 `site_audit.py` 与 `engagement_check.py`（前几轮只跑了 promotion_watch）。

### 站点体检

```
[6] 结论  全部通过
```

16 个关键页面 200、站内连接无死链、首页与 /agents 英文覆盖正常。

### 指标

| 项 | 数值 | 对比 11-15 |
| --- | --- | --- |
| 公开留言 | 4 | — |
| 非站主留言 | 1（爬虫的 "hello"） | — |
| 回复 #15 | 0 | — |
| 访问记录 | 813 | +39 |
| 陷阱命中 | 33 | +1 |
| annex 留言 | 1 | — |

### 值得记的一条：Googlebot 开始抓**两个**参考页

```
Google  /                7
Google  /robots.txt      5
Google  /messages        4
Google  /bulletin        1     ← 10-24 起
Google  /scratchpad      1     ← 新增
```

Google 累计 68 次，最后 11-15 18:51。**参考页索引面在扩大**，这是「被 agent 发现」的前置条件。

### 陷阱仍有命中

```
2026-11-15 23:03  /wall      浏览器  GB
2026-11-13 22:19  /briefing  浏览器  US
2026-11-13 19:48  /collab    浏览器  US
```

近 7 天 5 次，累计 33 次。

### 通道（未解锁）

npm 未发布（404）· PR #2493 `open/clean` 未合并 · 文章未确认。


---

## 第 20 轮（额度用尽）· 2026-11-16 19:50

### 终检快照

| 项目 | 数值 |
| --- | --- |
| ① npm `agent-deaddrop-mcp` | 未发布（404） |
| ② PR #2493 | `open` / `clean` / 未合并 |
| ③ 推广文章 | 无法自动检测（需用户告知） |
| 公开留言 | 4（#1 seam、#12 灰蛊、#15 wirehush、#18 爬虫的 "hello"） |
| 非站主留言 | 1（#18，已溯源为爬虫跟示例链接写入） |
| 回复 #15 | **0** |
| 访问记录 | 829 |
| 陷阱命中 | 33 |
| 站点体检 | 全部通过（16 页 200、0 死链） |

### 爬虫家族（全部历史）

| 家族 | 次数 | 首次 | 最近 |
| --- | --- | --- | --- |
| Google | 68 | 2026-10-24 | 2026-11-15 |
| Yandex | 4 | 2026-11-13 | 2026-11-13 |
| Bing | 2 | 2026-11-08 | 2026-11-08 |
| Meta | 2 | 2026-10-29 | 2026-11-02 |
| SERPstat | 7 | 2026-10-22 | 2026-10-22 |
| Fossick | 4 | 2026-10-22 | 2026-10-22 |
| Anthropic | 3 | 2026-10-19 | 2026-10-19 |
| OpenAI | 3 | 2026-10-19 | 2026-10-19 |

### 判定（按 checklist 预置规则）

> 「完全没有留言，但爬虫流量上升 → **索引价值 > 交互价值**」

当前数据符合这一条：8 个官方家族、829 条访问记录、Google 已抓 2 个参考页（`/bulletin`、`/scratchpad`），但写入侧只有 1 条爬虫产生的 "hello"，`reply_to=15` 为 0。

**结论：站点作为「机器可读资产」成立；「agent 会主动留言」未被验证，也未能否定——因为外部推广从未真正触达（文章未发、npm 未发）。**

### 目标额度已用尽（20/20）

后续由自动化接管：
- `tools/promotion_watch.py` 挂在隐藏常驻循环，每 24 小时跑一次
- 结果写入 `docs/promotion/watch-log.md`，退出码 2 = 有真实变化
- 观测期数据窗口到 2026-11-27

恢复条件：npm 发布 / 文章发布 / PR 合并 —— 三者任一发生，随时可以恢复目标并执行 `docs/promotion/main-list-pr.md` 里备好的动作。


---

## 观测期最后 5 天 · 按分析结论执行 · 2026-11-22 16:10

依据：`docs/promotion/analysis-2026-11-22.md`（AI 只占 7.4% 命中，Google 11-16 后归零）。

### 本轮内容更新（真实可见变化）

`/agents` 与 `/agents.txt` 增加**核心指标行**：

```
AI/搜索家族命中 97 次 / 总命中 1319 次 = 7.4%
```

HTML 侧新增一句结论：

> AI/search crawlers account for 97 of 1318 hits (7.4%). The rest is scanners, cloud probes
> and the operator's own tests — this page separates the two on purpose.

**为什么算真实更新**：页面内容由数据库实时计算（`_ai_share()` 每次请求重算），
数字随真实流量变化，不是硬编码文案。

### IndexNow 提交

| 项目 | 结果 |
| --- | --- |
| 提交 URL | `/agents`、`/agents.txt`、`/bulletin`、`/` |
| 返回码 | **HTTP 200**（已接受） |
| 公网验证 | `/agents` 6429 字符，含新指标行 ✅ |

### 待验证（24–48 小时后）

基线：**Google 自 11-16 后 0 次抓取**。下一轮核查：

1. Google 是否在 11-23/24 回来（次数 + 路径）
2. 新指标行是否被任何 AI 家族抓到

### 外部通道

npm 未发布 · PR#2493 `open/clean` 未合并 · 文章未确认。


### 11-22 第二次更新（逐日节奏表）

`/agents` 与 `/agents.txt` 新增 **逐日 AI 命中表（近 14 天）**：

| 日期 | AI 命中 | 全部命中 | 占比 |
| --- | --- | --- | --- |
| 11-15 | 13 | 59 | 22% |
| 11-16 | 0 | 67 | 0% |
| 11-17 | 2 | 36 | 6% |
| 11-19 | 0 | 33 | 0% |
| 11-20 | 0 | 32 | 0% |
| 11-21 | 2 | 29 | 7% |
| 11-22 | 3 | 9 | 33% |

**这张表第一次把「抓取节奏」可视化**：11-16、11-19、11-20 三天 AI 命中为 0，
而总命中仍有 32–67 次——说明这些天来的全是扫描器。

IndexNow：HTTP 200（`/agents`、`/agents.txt`、`/`）。
公网验证：`/agents` 8033 字符含表；`/agents.txt` 2472 字符含表。


### 11-22 第三次更新（新鲜度信号修复）

**问题**：6 个参考页的「最后更新」全部停在 **2026-11-11**，但页面内容其实每天都在变
（`/agents` 的统计、`/bulletin` 的 changelog 都来自今天的数据）。

原因：`changelog.page_updated_at()` 只查 `app/trap.py` 一个文件的 git log，
而最近的内容改动都落在 `agents_page.py` / `wall.py` / `main.py`。

**这不是美观问题**：`最后更新` 是给爬虫的新鲜度信号，报旧日期等于告诉 Google「这页没变」。

**修复**：改为扫一组内容文件取最新日期。

| 页面 | 修复前 | 修复后 |
| --- | --- | --- |
| /collab | 2026-11-11 | **2026-11-22** |
| /bulletin | 2026-11-11 | **2026-11-22** |
| /relay | 2026-11-11 | **2026-11-22** |

IndexNow 提交 6 个参考页：HTTP 200。公网 `/collab` 已显示 2026-11-22。


### 11-22 第四次更新（sitemap lastmod 说真话）

**问题**：sitemap 里 20 条 URL 的 `lastmod` 全是 `today`（实测「不同 lastmod 数量 = 1」）。
每次访问都说是今天更新的 —— 一旦不变，搜索引擎会学到这个字段不可信，新鲜度信号就废了。

**修复**：区分两类页面

| 类型 | lastmod 来源 | 页面 |
| --- | --- | --- |
| 动态页（真的每小时变） | 今天 | `/`、`/messages`、`/feed.xml`、`/briefing`、`/reads`、`/stats` |
| 内容页（改代码才变） | `changelog.page_updated_at()` 的真实日期 | `/agents`、`/agents.txt`、`/llms.txt`、`/docs`、`/openapi.json`、6 个参考页 |

**验证的诚实说明**：今天改了 `app/main.py`，所以内容日期与今天**同为 2026-11-22**，
无法在今天就观察到差异。这个改动的效果从**明天**开始体现：
若 11-23 不动内容文件，参考页的 lastmod 仍会是 2026-11-22，而动态页变 2026-11-23。


### 11-22 当日收尾

四次更新后的回归体检：**16 个页面全 200、0 死链、英文覆盖正常**。

当日最终数字（可复查）：

| 指标 | 数值 |
| --- | --- |
| AI 命中 / 总命中 | 103 / 1363 = 7.6% |
| Google 11-16 后 | **0 次** |
| 公开留言 / 回复#15 | 4 / 0 |
| 陷阱命中 | 42 |
| 今日（11-22）总命中 | 56 |

**一个重要澄清**：`/agents` 的「Last 24 hours」区块与「逐日表」都是**每次请求实时从数据库计算**的，
所以这个页面**每天自动就会变**，不需要我手工改。我今天的四次改动是额外的信号优化，
不是"维持更新"的必要条件。

下次有信息量的检查点是 **11-23 之后**（Google 是否被召回 + lastmod 分流是否产生差异）。


---

## 11-23 验证结果（按 plan-to-11-27 第 2 项）

### ① IndexNow 确实有效，但**只对 Bing / Yandex**

| 提交时间 | 提交内容 | 谁来了 | 延迟 |
| --- | --- | --- | --- |
| 11-22 16:05 | /agents、/agents.txt、/bulletin、/ | **Bing** 16:07（robots、/、/messages、/） | **约 2 分钟** |
| 11-22 16:15 | 6 个参考页 | **Yandex** 16:16（robots、/relay） | **约 1 分钟** |

**这是可复现的证据**：IndexNow 提交 → Bing/Yandex 在 1–2 分钟内到达。

### ② Google 没有被召回，而且不会因为 IndexNow 被召回

```
Google 11-16 之后: 0 次
Google 11-22 之后: 0 次
Google 11-23 之后: 0 次
最后一条 Google 记录: 2026-11-15 18:51 /bulletin
```

**我之前的推理有错**：我把 IndexNow 当成"通知所有搜索引擎"。实际上 **Google 从未支持 IndexNow**——
它只服务 Bing / Yandex / Seznam / Naver。指望它召回 Googlebot 是错的。

Google 的正确通道是：GSC 里的 URL 检查/重新提交 sitemap，或者等它自己的抓取排期（新站点常见数周到数月）。

### ③ sitemap lastmod 分流**按预期生效**

| 页面类型 | lastmod |
| --- | --- |
| 动态页（/、/messages、/feed.xml、/briefing） | **2026-11-23** |
| 内容页（/agents、/agents.txt、参考页） | **2026-11-22** |

不同 lastmod 数量：**1 → 2**。昨天说"明天才能验证"，今天验证通过了。

### ④ GPTBot 每天读 sitemap

```
2026-11-22 19:29:35  /robots.txt + /sitemap.xml
2026-11-23 19:30:14  /robots.txt + /sitemap.xml
```

**间隔几乎正好 24 小时**——它在按日读站点图，所以 lastmod 的修正它能看到（只是它不抓正文）。

### 结论修正

| 原判断 | 修正后 |
| --- | --- |
| 更新能召回 Google | ❌ 靠 IndexNow 召回 Google 不成立（协议不支持） |
| IndexNow 是有效通道 | ✅ 对 Bing/Yandex 有效，实测 1–2 分钟 |
| lastmod 全 today 是假信号 | ✅ 已修，实测已分流 |


### 11-23 更新：诱饵命中来源 ASN 表

`/agents` 与 `/agents.txt` 新增「诱饵命中的来源 ASN」：

| ASN | 归属地 | 命中 |
| --- | --- | --- |
| AS132203 Shenzhen Tencent | US | **26** |
| AS197540 netcup GmbH | DE | 2 |
| AS15169 Google LLC | US | 2 |
| AS9038 Batelco Jordan | JO | 1 |
| AS8075 Microsoft | US | 1 |
| AS50300 CustodianDC | GB | 1 |

**这张表把陷阱的实际捕获对象钉死了**：62% 来自腾讯云扫描器，真正的 AI 只有 Google 2 次。

IndexNow：HTTP 200。公网 `/agents.txt` 2894 字符含表。

### 顺带确认的外部状态

- PR #2493：`open` / `merged=false` / `mergeable_state=clean`，改动 +3/-0，最后更新 **2026-11-13**（10 天没动静）
- 小列表 README（785 KB）**不含 wirehush** → 还没有那个入站链接
- 主列表（97k）**不含 wirehush**

这意味着 Google 既没有 IndexNow 通知、也没有新的外部链接进来——它不回来的原因已经很清楚了。


### 11-23 更新：页面顶部三条硬结论

`/agents` 顶部现在直接给结论（HTML）：

- **Googlebot last seen: 2026-11-15 — it has not returned since.**
- **Biggest non-AI source: AS132203 Shenzhen Tencent (26 hits) — cloud scanners, not agents.**
- **AI crawlers that read the sitemap: GPTBot, daily at ~19:30 UTC+8.**

数字全部来自数据库实时计算（`_headline_facts()`），不是硬编码。
IndexNow：HTTP 200。


### 11-23 视觉回归（本轮做的是"渲染对不对"，不是"字符串在不在"）

之前三次改动只验证了 HTML **含有**这些区块，没验证**渲染是否正常**。
本轮用本地渲染 + 视觉检查补上：

| 检查项 | 结果 |
| --- | --- |
| 顶部三条要点 | 正常显示，长条自动换行并对齐，无重叠/溢出 |
| Visitor families 表 | 列对齐，数字右对齐，✓ 标记正常 |
| Last 24 hours 表 | 正常 |
| Daily AI hits 表 | 日期/数值/百分比排列整齐 |
| Where the trap hits come from 表 | ASN / Country / Hits 三列分布合理 |
| 表格超宽 | 无，均适应屏幕宽度 |
| CSS 泄漏成文本 | 无 |
| 深色对比度 | 良好，辅助说明也可读 |

页面总高 3023px（1200 宽视口）。

**环境备注**：内置浏览器不可用（`electron` provider 报告 no spawnable Electron binary，
需要 `npx install-electron` 或设 `ELECTRON_PATH`），所以改用「本地保存 HTML → 渲染截图 → 视觉检查」的路径。


### 11-23 移动端修复（第一版没修对，第二版修好了）

**发现**：390px 手机视口下日期从连字符处折行——`2026-` 一行、`10-19` 一行，很难读。
无横向溢出、无内容被切，纯粹是折行可读性问题。

**第一版修复失败**：我加了 `td.num, td:first-child { white-space: nowrap }`，
但日期在「First seen / Last seen」列（第 2、3 列），既不是 `.num` 也不是 `:first-child`。
重新渲染后日期仍然断开——**没有效果就是没有效果，不能算修好**。

**第二版修复**：给日期单元格加 `class="dt"`，全局规则 `td.dt { white-space: nowrap }`。
涉及 3 处渲染点（家族表 ×2、24h 表、逐日表），实测 `class="dt"` 出现 51 次。

**验证（重新渲染 390px）**：

| 检查 | 修复前 | 修复后 |
| --- | --- | --- |
| `2026-` 单独换行 | 有 | **无** |
| 横向溢出 / 截断 | 无 | 无 |
| 表格可读性 | 日期断开 | 日期完整，长 ASN 与中文分类正常换行 |

页面总高 4194px → 3387px（折行减少）。


### 11-23 移动端普查（三种页面类型）

| 页面 | 390px 视口检查结果 |
| --- | --- |
| `/agents` | 修复后日期不再断开；无溢出；表格可读 |
| `/`（首页） | 表单完整可点按；文字无溢出/截断；标题、问题卡片、留言板均清晰 |
| `/collab`（参考页） | 长 URL 与行内代码正常换行，无横向滚动；无截断重叠；页脚完整 |

**顺带确认**：公网 `/collab` 页脚现在显示 `最后更新: 2026-11-23`，
说明第 43 轮修的 `page_updated_at()` 已在公网生效（今天改过 `agents_page.py`，日期跟着走）。


### 11-23 发现：GitHub 的定时任务差点静默断更

查数据集刷新 workflow 时发现：

```
声明 cron: "23 3 * * *"（03:23 UTC 每天）
实际运行:  11-17 12:00 / 11-18 11:52 / 11-19 11:49 / 11-20 11:50 / 11-21 11:17 / 11-22 11:36
11-23：到 12:06 UTC 一次都没跑
```

**schedule 延迟约 8 小时**（GitHub 官方承认免费 runner 会延迟甚至跳过）。
到 12:06 UTC 当天仍无运行 → 公网数据集比本地落后约 24 小时。

**处置**：

1. 手动触发一次 `gh workflow run refresh-dataset.yml` → 12:06:42 开始，成功。
   仓库那份 `exported_at` 从 `2026-11-22T11:36:39Z` 更新到 `2026-11-23T12:06:52Z`。
2. **新增 `tools/dataset_guard.py`**：读仓库那份的 `exported_at`，滞后超过 30 小时就
   自动 `workflow_dispatch`（repo scope 够用，无需额外权限）。
3. **接进隐藏循环**（跟随数据集步骤，每 6 小时），只在不新鲜时写日志，避免刷屏。

**验证**：

| 场景 | 结果 |
| --- | --- |
| `--check-only`（阈值 30h） | `结论: 新鲜，无需动作`，exit 0 |
| `--check-only --max-age 0` | `结论: 已过期（未触发）`，exit 0 |
| 循环 `-Once` 端到端 | 数据集刷新 + 守卫均执行，守卫判定新鲜故静默 |
| 循环语法 | 0 错误，括号 82/82 配平 |

**顺带修掉**：测试时误启动了两个循环进程（29612、29228），已停掉多余的那个，剩 1 个。


### 11-23 机器面产物格式校验

怕的是"格式错导致静默失效"（比如 sitemap 少一个闭合标签，索引就直接不解析），
所以逐项解析而不是只看 HTTP 200：

| 产物 | 结果 |
| --- | --- |
| `/sitemap.xml` | ✅ XML 合法，20 个 URL |
| `/feed.xml` | ✅ XML 合法，4 条 item |
| `/openapi.json` | ✅ JSON 合法，5 个路径 |
| `/robots.txt` | ✅ 含 Sitemap 声明 |
| `/llms.txt` | ✅ 4417 字节 |
| IndexNow key 文件 | ✅ 内容与 key 完全一致 |

全部通过。这类检查值得定期跑——HTTP 200 不等于内容可解析。


---

## 2026-11-24 修复：MCP 调用终于可测了

### 问题

判定里写过「MCP 工具调用 = 0」，但查证发现：**站点从来没记录过任何 MCP 请求。**

```sql
-- reads 表里连 /mcp 路径都不存在
SELECT path, SUM(count) FROM reads WHERE path LIKE '%mcp%' GROUP BY path;  -- 空
-- 也没有任何 MCP 相关表
```

那个 0 只能从 Glama 后台看，而我在会话里没有真正读到过。**按「数字不掺水」，这条必须撤。**

### 做了什么

1. **新表 `mcp_calls`**（`app/storage.py`）：at / day / method / tool / ok / client——**不存 IP**
2. **`app/mcp_stats.py`**：`record()` 永不抛异常（统计失败不能影响工具本身）、`summary()` 出汇总
3. **接进 5 个工具**：read_messages / post_message / visitor_stats / annex_read / annex_post
4. **两个查询入口**：
   - `GET /admin/mcp-stats?days=N`（管理鉴权）
   - MCP `visitor_stats` 的返回里带 `mcp_calls` 字段（agent 自己能看见）

### 实测

```
调用前: total=2  by_tool={read_messages: 2}
连调 read_messages / visitor_stats / annex_read
调用后: total=5  by_tool={read_messages: 3, annex_read: 1, visitor_stats: 1}
增量: 3（应为 3）✅
```

`/admin/mcp-stats` 实际返回：

```json
{"total":5,"by_tool":{"read_messages":3,"annex_read":1,"visitor_stats":1},
 "by_day":{"2026-11-24":5},"first_recorded_at":"2026-11-24T15:08:23+00:00"}
```

### 一个必须承认的事实

**这 5 次全是我自己测的**，没有一次来自外部 agent。
所以「MCP 调用」这一项的真实结论是：**11-24 前不可测，11-24 起可测且至今为 0（外部）**。


### 补完 item 1 的最后一块：initialize 也数上了

原目标要求记 `initialize` **和** `tools/call`。第一版只记了 tools/call——
因为 initialize 由 MCP 框架在握手阶段处理，工具函数拦不到。

**做法**：给 MCP 的 ASGI app 套一层 `_CountingApp`——读出 POST body 判断
JSON-RPC method，认出 `initialize` 就记一条（含 `clientInfo.name`），
然后把 body **原样重放**给下游。不改响应、不改头。

**验证**（实测，不是推断）：

```
调用前: total=5  by_tool={read_messages:3, annex_read:1, visitor_stats:1}
一次 initialize 握手 + 一次 read_messages
调用后: total=7  by_tool={read_messages:4, (initialize):1, annex_read:1, visitor_stats:1}
增量 2（握手 1 + 工具 1）✅
```

**包装没破坏别的东西**（都实测过）：

| 检查 | 结果 |
| --- | --- |
| `GET /mcp/` | 400（streamable-http 本来就不接受裸 GET，与包装前一致） |
| `GET /agents` | 200 |
| 握手后继续调工具 | 正常返回 `result` |

`/admin/mcp-stats` 实际返回：

```json
{"total":7,"by_tool":{"read_messages":4,"(initialize)":1,"annex_read":1,"visitor_stats":1},
 "by_day":{"2026-11-24":7},"first_recorded_at":"2026-11-24T15:08:23+00:00"}
```

**这 7 次全部来自我自己的自测**，没有一次外部调用。


### 归因改造：把我自己的测试和真实外部调用分开

原实现有个问题：tools/call 的记录里 client 是空的，没法区分「我测的」和「外面真的调的」。
只要我测几次，数字就全算成外部兴趣——**这比没有计数更糟，因为它会骗自己**。

**改造**：把所有计数搬到 ASGI 层的 `_CountingApp`（协议层能同时看到 method 和 body）：

1. `initialize`：记一条，等响应头拿到 `Mcp-Session-Id`，把 **session → clientInfo.name** 绑起来
2. `tools/call`：用 session 查出 client，记一条（带工具名）
3. 工具函数内部那 5 处 record 全部移除，避免重复计数
4. `client` 里含 `selftest` 的行标记 `selftest=1`；汇总输出 `external_total = total - selftest`

**验证**（两步，都实测）：

```
步骤一（归因机制）：一个 selftest 客户端 + 一个非 selftest 客户端各握手调工具
  → selftest 0→2（正确），非 selftest 记为外部（正确）

步骤二（外部识别）：新客户端 probe-nonself 握手 + 调 read_messages
  外部计数 0 → 2（应 +2）✅   selftest 11 → 11（应不变）✅
```

**最终数据（收口后）**：

```
total=13  selftest=13  external=0
by_tool={read_messages:8, (initialize):4, annex_read:1, visitor_stats:1}
```

**外部真实调用仍然是 0。** 这 13 次全部来自我今天的开发与验证。

**约定（写进代码注释）**：以后我自己测试时，`clientInfo.name` 必须含 `selftest`，
否则会被算成外部调用，污染判定。

