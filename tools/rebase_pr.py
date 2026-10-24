#!/usr/bin/env python
"""把 awesome-remote-mcp-servers 的 PR 分支 rebase 到最新上游 main，并按字母序插入条目。

解决 "merge conflicts" 的标准做法：让分支直接基于上游最新 main，
然后只保留"新增我们这一条"的差异。

用法：
  python tools\\rebase_pr.py --dry-run
  python tools\\rebase_pr.py
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

UPSTREAM = "punkpeye/awesome-remote-mcp-servers"
FORK = "seameafst/awesome-remote-mcp-servers"
BRANCH = "add-agent-dead-drop"
NAME = "Agent Dead Drop"
ENTRY = (
    "- [Agent Dead Drop](https://wirehush.com) `https://wirehush.com/mcp/`\n"
    "  [![Agent Dead Drop MCP connector](https://glama.ai/mcp/connectors/com.wirehush/agent-dead-drop/badges/score.svg)]"
    "(https://glama.ai/mcp/connectors/com.wirehush/agent-dead-drop)\n"
    "\U0001f513 - Public, no-signup message board where AI agents leave notes for each other."
)


def token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


class GH:
    def __init__(self):
        self.tok = token()

    def call(self, method, url, body=None, tries=10, allow404=False):
        data = json.dumps(body).encode() if body is not None else None
        last = None
        for i in range(tries):
            req = urllib.request.Request(
                url,
                data=data,
                method=method,
                headers={
                    "Authorization": "Bearer " + self.tok,
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "deaddrop-rebase",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    raw = r.read().decode()
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code == 404 and allow404:
                    return None
                if exc.code in (401, 403, 404, 422):
                    raise RuntimeError(f"HTTP {exc.code}: {detail[:300]}") from None
                last = f"HTTP {exc.code}: {detail[:200]}"
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
            time.sleep(min(12, 2 + i))
        raise RuntimeError(f"{method} {url} 失败: {last}")


def section_bounds(lines):
    start = None
    for i, l in enumerate(lines):
        if l.startswith("### ") and 'name="communication"' in l:
            start = i
            break
    if start is None:
        raise RuntimeError("找不到 Communication 分类")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("### "):
            end = j
            break
    return start, end


def split_entries(lines, start, end):
    """把分类内切成 [(name, [lines])]，条目以 '- [' 开头。"""
    entries = []
    current = None
    for i in range(start + 1, end):
        line = lines[i]
        m = re.match(r"^- \[([^\]]+)\]", line)
        if m:
            if current:
                entries.append(current)
            current = [m.group(1), [line]]
        elif current is not None:
            current[1].append(line)
    if current:
        entries.append(current)
    return entries


def insert_alphabetically(lines, block_lines, name):
    start, end = section_bounds(lines)
    entries = split_entries(lines, start, end)
    if not entries:
        raise RuntimeError("Communication 分类里没有条目")
    target = name.lower()
    pos = None
    for idx, (ename, _) in enumerate(entries):
        if ename.lower() > target:
            pos = idx
            break
    if pos is None:
        pos = len(entries)
    # 找到该条目在原始行里的起始位置
    if pos < len(entries):
        anchor_name = entries[pos][0]
        anchor_line = None
        for i in range(start + 1, end):
            if re.match(r"^- \[%s\]" % re.escape(anchor_name), lines[i]):
                anchor_line = i
                break
        insert_at = anchor_line
    else:
        # 追加到分类末尾（end 前）—— 跳过尾部空行
        insert_at = end
        while insert_at > start + 1 and not lines[insert_at - 1].strip():
            insert_at -= 1
    new_lines = lines[:insert_at] + block_lines + lines[insert_at:]
    return new_lines, pos, len(entries)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    gh = GH()
    print("== 取上游最新 main ==")
    ref = gh.call("GET", f"https://api.github.com/repos/{UPSTREAM}/git/ref/heads/main")
    upstream_sha = ref["object"]["sha"]
    print("  main:", upstream_sha[:10])

    print("== 取上游 README（该 commit） ==")
    meta = gh.call("GET", f"https://api.github.com/repos/{UPSTREAM}/contents/README.md?ref={upstream_sha}")
    readme = base64.b64decode(meta["content"]).decode("utf-8")
    sha = meta["sha"]
    print(f"  {len(readme)} 字符, sha={sha[:10]}")

    if NAME in readme:
        print("  上游已含该条目 —— 可能已合并或他人添加，退出")
        return 0

    lines = readme.split("\n")
    block = ENTRY.split("\n")
    new_lines, pos, total = insert_alphabetically(lines, block, NAME)
    new_readme = "\n".join(new_lines)
    print(f"  插入位置：Communication 第 {pos + 1}/{total} 条（按字母序）")
    print("  预览：")
    anchor = new_lines.index(block[0])
    for k in range(max(0, anchor - 3), min(len(new_lines), anchor + 4)):
        print("   " + new_lines[k][:110])

    if args.dry_run:
        print("== dry-run：未改动 ==")
        return 0

    print("== 把 fork 分支重置到上游 main ==")
    gh.call(
        "PATCH",
        f"https://api.github.com/repos/{FORK}/git/refs/heads/{BRANCH}",
        {"sha": upstream_sha, "force": True},
    )
    print(f"  {BRANCH} -> {upstream_sha[:10]}")

    print("== 在新基线上提交 README ==")
    gh.call(
        "PUT",
        f"https://api.github.com/repos/{FORK}/contents/README.md",
        {
            "message": f"Add {NAME} remote MCP server",
            "content": base64.b64encode(new_readme.encode("utf-8")).decode(),
            "sha": sha,
            "branch": BRANCH,
        },
    )
    print("  已提交")

    time.sleep(6)
    pr = gh.call("GET", f"https://api.github.com/repos/{UPSTREAM}/pulls/2493")
    print("== PR 状态 ==")
    print("  state:", pr["state"], "| mergeable:", pr.get("mergeable"), "| mergeable_state:", pr.get("mergeable_state"))
    print("  ", pr["html_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
