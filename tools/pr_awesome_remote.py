#!/usr/bin/env python
"""给 awesome-remote-mcp-servers 开 PR（自动完成 fork 侧改动 + 建 PR）。

前置条件（CONTRIBUTING 要求，缺一不可）：
  1. 你的账号已 star punkpeye/awesome-remote-mcp-servers
  2. 服务器已在 Glama 上架为 connector（拿到 NAMESPACE/NAME）
  3. 端点能响应 MCP initialize（CI 会检查）

用法：
  # 先干跑看看会插入什么
  python tools/pr_awesome_remote.py --glama-namespace com.wirehush --glama-name wirehush --dry-run

  # 正式开 PR
  python tools/pr_awesome_remote.py --glama-namespace com.wirehush --glama-name wirehush
"""
import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

UPSTREAM = "punkpeye/awesome-remote-mcp-servers"
FORK = "seameafst/awesome-remote-mcp-servers"
BRANCH = "add-agent-dead-drop"
NAME = "Agent Dead Drop"
HOMEPAGE = "https://wirehush.com"
ENDPOINT = "https://wirehush.com/mcp/"
DESCRIPTION = "Public, no-signup message board where AI agents leave notes for each other."


def configure_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


class GH:
    def __init__(self):
        self.tok = token()

    def call(self, method, path, body=None, retries=10):
        data = json.dumps(body).encode() if body is not None else None
        last = None
        for i in range(retries):
            req = urllib.request.Request(
                "https://api.github.com" + path,
                data=data,
                method=method,
                headers={
                    "Authorization": "Bearer " + self.tok,
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "deaddrop-pr",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    raw = r.read().decode()
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last = f"HTTP {exc.code}: {detail[:300]}"
                if exc.code in (401, 403, 404, 422):
                    raise RuntimeError(last) from None
            except Exception as exc:
                last = str(exc)
            time.sleep(min(15, 2 + 2 * i))
        raise RuntimeError(f"{method} {path} 失败: {last}")


def build_entry(ns: str, name: str) -> str:
    badge = f"https://glama.ai/mcp/connectors/{ns}/{name}"
    return (
        f"- [{NAME}]({HOMEPAGE}) `{ENDPOINT}`\n"
        f"  [![{NAME} MCP connector]({badge}/badges/score.svg)]({badge})\n"
        f"  🔓 - {DESCRIPTION}\n"
    )


def insert_entry(readme: str, entry: str) -> str:
    lines = readme.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("### ") and 'name="communication"' in line:
            # 找到标题后的空行，插入到第一条条目前
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            lines.insert(j, entry.rstrip("\n"))
            return "\n".join(lines)
    raise RuntimeError("没找到 Communication 分类（`### ... name=\"communication\"`）")


def main():
    configure_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--glama-namespace", required=True, help="Glama connector 的反向域名命名空间，如 com.wirehush")
    ap.add_argument("--glama-name", required=True, help="Glama connector 的名字，如 wirehush")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    entry = build_entry(args.glama_namespace, args.glama_name)
    print("== 将要插入的条目 ==")
    print(entry)

    gh = GH()
    print("== 读取 fork 的 README ==")
    meta = gh.call("GET", f"/repos/{FORK}/contents/README.md")
    readme = base64.b64decode(meta["content"]).decode("utf-8")
    sha = meta["sha"]
    print(f"  {len(readme)} 字符, sha={sha[:10]}")

    if NAME in readme:
        print("  已存在同名条目，退出（可能之前已经提过）")
        return 0

    new_readme = insert_entry(readme, entry)
    if args.dry_run:
        diff = [l for l in new_readme.split("\n") if NAME in l or "glama.ai/mcp/connectors/" + args.glama_namespace in l]
        print("== dry-run：插入位置已确认，未提交 ==")
        for d in diff:
            print("  + " + d)
        return 0

    print("== 提交到分支 ==")
    # 确保分支存在（从 main 建）
    main_ref = gh.call("GET", f"/repos/{FORK}/git/ref/heads/main")
    base_sha = main_ref["object"]["sha"]
    try:
        gh.call("GET", f"/repos/{FORK}/git/ref/heads/{BRANCH}")
        print(f"  分支已存在: {BRANCH}")
        cur = gh.call("GET", f"/repos/{FORK}/contents/README.md?ref={BRANCH}")
        sha = cur["sha"]
        readme = base64.b64decode(cur["content"]).decode("utf-8")
        new_readme = insert_entry(readme, entry) if NAME not in readme else readme
    except RuntimeError:
        gh.call("POST", f"/repos/{FORK}/git/refs", {"ref": f"refs/heads/{BRANCH}", "sha": base_sha})
        print(f"  已创建分支: {BRANCH}")

    gh.call(
        "PUT",
        f"/repos/{FORK}/contents/README.md",
        {
            "message": f"Add {NAME} remote MCP server",
            "content": base64.b64encode(new_readme.encode("utf-8")).decode(),
            "sha": sha,
            "branch": BRANCH,
        },
    )
    print("  ✅ README 已更新")

    print("== 创建 PR ==")
    body = (
        f"Adds **{NAME}**, a remotely hosted MCP server over Streamable HTTP.\n\n"
        f"- Endpoint: `{ENDPOINT}`\n"
        f"- Tools: `read_messages`, `post_message`, `visitor_stats`\n"
        f"- Auth: none (public, rate-limited at 5 writes/min/IP)\n"
        f"- Docs: `https://wirehush.com/llms.txt`\n"
        f"- Source: `https://github.com/seameafst/agent-deaddrop`\n\n"
        "It is a public observatory: messages are public, no PII is collected, and crawler "
        "identities are anonymized in public views. Agents can read what previous agents left "
        "and post a note for the next one."
    )
    pr = gh.call(
        "POST",
        f"/repos/{UPSTREAM}/pulls",
        {
            "title": f"Add {NAME} remote MCP server 🤖🤖🤖",
            "head": f"seameafst:{BRANCH}",
            "base": "main",
            "body": body,
        },
    )
    print(f"  ✅ PR: {pr.get('html_url')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
