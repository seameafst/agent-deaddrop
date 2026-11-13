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




