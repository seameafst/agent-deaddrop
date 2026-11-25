### 外部证据（2026-11-25 找到）：目录健康检查**不会**调用工具

在 npm 包 `hermoso` 的 `mcp/http.mjs`（公开 CDN 源码）里，有大量关于
「目录 / 健康检查爬虫怎么打 MCP 端点」的实测注释，其中直接点名 Glama：

> **Glama's connector health check (glama.ai/mcp/connectors/...)** sends UA `"node"` — bare,
> exactly what Gemini CLI sends — so the UA rule above cannot see it, and since the inversion
> it has been 401 every ~20 min and the listing reads **"Status: Unhealthy"**.
> ... the one pre-inversion [mcp-anon] line on that cadence names clientInfo **"mcpdd"** (2026-09-25T13:34:47).

还有一条更关键的：

> A tokenless caller may run the **ZERO-SPEND MCP handshake — initialize, notifications/initialized,
> ping, tools/list** — so a directory (registry.modelcontextprotocol.io) or an agent deciding whether
> to connect sees the REAL tool catalog first. **Everything that spends (tools/call) stays strictly
> bearer-gated.**

以及：

> **A HANDSHAKE IS NOT USE.** ... Only a `tools/call` is somebody doing something, so only a
> `tools/call` stamps.

#### 这改变了什么

1. **目录健康检查在设计上就不调用 `tools/call`** —— 它们是零成本探测，
   只做 `initialize` / `initialized` / `ping` / `tools/list`。
   所以我们看到「Glama 三次 initialize、零 tools/call」**是预期行为，不是冷淡信号**。
2. 我之前把「零 tools/call」读成「没被使用」，这个解读方向对，但**归因错了**：
   它不是"有人连进来却不用"，而是"来的是探测器，探测器的定义就是不调用工具"。
3. Glama 的健康判定看的是**握手是否成功**（401 → "Status: Unhealthy"）。
   我们返回 200，所以它那边应该标为健康。
4. 我们漏了一个信号：**`tools/list`**。目录探测通常会读一次工具目录，
   这才是"看到了什么"，与 initialize（"连得上"）和 tools/call（"真的用了"）不是一回事。

**待办**：把 `tools/list` 也计入统计，形成三段式：
`initialize`（连上）→ `tools/list`（看到了目录）→ `tools/call`（真的用了）。
