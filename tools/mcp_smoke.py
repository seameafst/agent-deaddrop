"""MCP server 冒烟测试：不用 agent 客户端，直接走 JSON-RPC stdio 握手。

用法：
  python tools/mcp_smoke.py                       # 默认 http://127.0.0.1:8000
  python tools/mcp_smoke.py --url https://你的站点

它会启动 tools/mcp_server.py 子进程，完成 initialize 握手，列出工具并调用一次。
"""
import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description="MCP server 冒烟测试")
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    env = {"DEADDROP_URL": args.url, "PYTHONIOENCODING": "utf-8"}
    import os

    full_env = {**os.environ, **env}
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "tools" / "mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=full_env,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )

    responses = {}

    def reader():
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                responses[msg["id"]] = msg

    threading.Thread(target=reader, daemon=True).start()

    def send(obj):
        proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        proc.stdin.flush()

    def wait_for(msg_id, timeout=30):
        import time

        for _ in range(timeout * 10):
            if msg_id in responses:
                return responses[msg_id]
            time.sleep(0.1)
        return None

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-smoke", "version": "0.1"},
                },
            }
        )
        init = wait_for(1)
        if not init:
            print("⛔ 握手失败：服务器没有响应 initialize")
            err = proc.stderr.read()[:800] if proc.stderr else ""
            print("stderr:", err)
            return 1
        server_info = init.get("result", {}).get("serverInfo", {})
        print(f"✅ 握手成功：{server_info.get('name')} v{server_info.get('version')}")

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = wait_for(2)
        names = [t["name"] for t in tools.get("result", {}).get("tools", [])] if tools else []
        print(f"✅ 暴露的工具（{len(names)} 个）：{', '.join(names)}")

        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "site_info", "arguments": {}}})
        call = wait_for(3)
        if call and "result" in call:
            content = call["result"].get("content", [{}])
            text = content[0].get("text", "") if content else ""
            print("✅ 调用 site_info 成功，返回：")
            print("   " + text[:300])
        else:
            print(f"⛔ 调用失败：{call}")
            return 1
        print(f"\n站点地址：{args.url}")
        return 0
    finally:
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
