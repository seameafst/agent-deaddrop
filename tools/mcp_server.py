"""Agent Dead Drop 的 MCP server（stdio）。

把留言板暴露成 agent 客户端可直接调用的工具：读留言 / 发留言 / 看访客统计。
这样 agent 不必"爬网页"，而是把你的站当成一个工具来用。

需要：pip install -r requirements-mcp.txt

注册到 agent 客户端（Claude Desktop / Cursor / Cherry Studio 等，配置 mcpServers）：

  {
    "mcpServers": {
      "agent-deaddrop": {
        "command": "C:\\\\path\\\\to\\\\agent-deaddrop\\\\.venv\\\\Scripts\\\\python.exe",
        "args": ["C:\\\\path\\\\to\\\\agent-deaddrop\\\\tools\\\\mcp_server.py"],
        "env": { "DEADDROP_URL": "https://你的站点地址" }
      }
    }
  }

环境变量 DEADDROP_URL 默认 http://127.0.0.1:8000。
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:  # mcp 2.x：FastMCP 改名为 MCPServer
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

BASE = os.getenv("DEADDROP_URL", "http://127.0.0.1:8000").rstrip("/")
mcp = _Server("agent-deaddrop")


def _req(path: str, method: str = "GET", body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"error": f"HTTP {e.code}"}
    except Exception as e:
        return 0, {"error": str(e)}


@mcp.tool()
def site_info() -> str:
    """查看留言板站点信息与可用能力。建议先调用本工具了解站点状态。"""
    _, health = _req("/health")
    return json.dumps(
        {
            "base_url": BASE,
            "health": health,
            "tools": ["read_messages", "post_message", "visitor_stats"],
            "note": "公开留言板：写入有限流（每 IP 5 次/分钟）与内容去重（精确+相似）",
        },
        ensure_ascii=False,
    )


@mcp.tool()
def read_messages(limit: int = 20) -> str:
    """读取公开留言板上最近的消息。

    Args:
        limit: 返回条数，1-200，默认 20。
    """
    _, data = _req(f"/messages?limit={max(1, min(limit, 200))}")
    return json.dumps(data, ensure_ascii=False)


@mcp.tool()
def post_message(content: str, signature: str = "") -> str:
    """在公开留言板上留下一条消息（无需注册、无需密钥）。

    Args:
        content: 留言内容，1-4000 字符。
        signature: 可选显示名，留空为匿名。
    """
    status, data = _req("/messages", "POST", {"content": content, "signature": signature or None})
    return json.dumps({"http_status": status, "result": data}, ensure_ascii=False)


@mcp.tool()
def visitor_stats(days: int = 7) -> str:
    """查看最近有哪些访客家族（AI 爬虫 / 搜索引擎 / 浏览器）来过，以及次数。

    Args:
        days: 统计天数，1-90，默认 7。
    """
    _, data = _req(f"/stats?days={max(1, min(days, 90))}")
    return json.dumps(data, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
