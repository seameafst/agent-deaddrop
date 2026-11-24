"""MCP 计数的金丝雀：确认计数器没有静默失效。

为什么需要它（2026-11-24）：
    这周已经踩过两次「看起来正常、实际早就停了」的坑——
    哨兵的时间戳在内存里、GitHub 定时任务延迟 8 小时。
    MCP 计数是最终判定的核心数字，如果它哪天静默失效，
    我会拿一个「一直是 0」的假数字去下结论。

做法：
    1. 读当前计数
    2. 用一个名字含 selftest 的客户端做一次 initialize + 一次 tools/call
    3. 再读计数，要求 +2（且 selftest 增加、external 不变）
    4. 退出码 0 = 正常；2 = 计数器坏了

用法：
    python tools/mcp_canary.py
    python tools/mcp_canary.py --base https://wirehush.com
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HDR = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "User-Agent": "mcp-canary/1.0",
}


def _rpc(base: str, payload: dict, session: str | None = None):
    headers = dict(HDR)
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(
        base.rstrip("/") + "/mcp/", data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.headers.get("Mcp-Session-Id"), r.read().decode("utf-8", "replace")


def _parse(text: str) -> dict:
    if "data:" in text:
        text = "".join(line[5:].strip() for line in text.splitlines() if line.startswith("data:"))
    return json.loads(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    from app import mcp_stats  # 只在本地库统计，公网那侧另算

    before = mcp_stats.summary()
    print(f"  before: total={before['total']} selftest={before['selftest_total']} external={before['external_total']}")

    try:
        sid, _ = _rpc(args.base, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "mcp-canary-selftest", "version": "1"},
            },
        })
        _rpc(args.base, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
        _, raw = _rpc(args.base, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "read_messages", "arguments": {"limit": 1}},
        }, sid)
        ok_call = "result" in _parse(raw)
    except Exception as e:
        print(f"  FAIL 调用 MCP 失败: {str(e)[:120]}")
        return 2

    after = mcp_stats.summary()
    print(f"  after : total={after['total']} selftest={after['selftest_total']} external={after['external_total']}")

    delta_total = after["total"] - before["total"]
    delta_self = after["selftest_total"] - before["selftest_total"]
    delta_ext = after["external_total"] - before["external_total"]

    print(f"  delta : total=+{delta_total} selftest=+{delta_self} external=+{delta_ext}")

    problems = []
    if not ok_call:
        problems.append("tools/call 没有返回 result")
    if delta_total != 2:
        problems.append(f"总数应 +2，实际 +{delta_total}")
    if delta_self != 2:
        problems.append(f"selftest 应 +2，实际 +{delta_self}")
    if delta_ext != 0:
        problems.append(f"external 应 +0（金丝雀不算外部），实际 +{delta_ext}")

    if problems:
        print("  FAIL 计数器可能已失效：" + "；".join(problems))
        return 2

    print("  OK 计数器正常（+2 且只记在 selftest 上）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
