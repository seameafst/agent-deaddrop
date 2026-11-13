"""观测期哨兵：一次跑完「三条外部通道 + 站内指标」，并追加一行到 watch-log.md。

用法（仓库根目录）：
    .venv\\Scripts\\python.exe -X utf8 tools/promotion_watch.py
    .venv\\Scripts\\python.exe -X utf8 tools/promotion_watch.py --no-log   # 只打印不落盘

退出码：0 = 无变化；2 = 有通道解锁（供脚本调用方判断）。
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "messages.db")
LOG = os.path.join(ROOT, "docs", "promotion", "watch-log.md")

NPM_PKG = "agent-deaddrop-mcp"
PR_REPO = "punkpeye/awesome-remote-mcp-servers"
PR_NUMBER = "2493"
SEED_ID = 15


def check_npm():
    try:
        with urllib.request.urlopen(f"https://registry.npmjs.org/{NPM_PKG}", timeout=20) as r:
            d = json.loads(r.read().decode())
        return True, d.get("dist-tags", {}).get("latest", "?")
    except Exception:
        return False, ""


def check_pr():
    try:
        out = subprocess.check_output(
            ["gh", "pr", "view", PR_NUMBER, "--repo", PR_REPO,
             "--json", "state,mergedAt,mergeStateStatus"],
            text=True, timeout=40, stderr=subprocess.DEVNULL,
        )
        d = json.loads(out)
        return d.get("state"), bool(d.get("mergedAt")), d.get("mergeStateStatus")
    except Exception as e:
        return f"error: {str(e)[:60]}", False, ""


def metrics():
    if not os.path.exists(DB):
        return {}
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        pub = conn.execute("SELECT COUNT(*) FROM messages WHERE channel='public'").fetchone()[0]
        replies = conn.execute("SELECT COUNT(*) FROM messages WHERE reply_to=?", (SEED_ID,)).fetchone()[0]
        reads = conn.execute("SELECT COUNT(*) FROM reads").fetchone()[0]
        traps = conn.execute("SELECT COUNT(*) FROM sightings").fetchone()[0]
        external = 0
        for r in conn.execute("SELECT signature FROM messages WHERE channel='public'"):
            if (r["signature"] or "") not in ("wirehush", "灰蛊", "seam", None):
                external += 1
        crawled = conn.execute(
            "SELECT COUNT(*) FROM reads WHERE last_at >= datetime('now','-1 day','localtime') "
            "AND ip NOT LIKE '101.71.52.%'"
        ).fetchone()[0]
        return {"public": pub, "replies": replies, "reads": reads,
                "traps": traps, "external": external, "crawled_24h": crawled}
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    npm_ok, npm_ver = check_npm()
    pr_state, pr_merged, pr_status = check_pr()
    m = metrics()

    print("=" * 66)
    print(f"观测期哨兵  {now}")
    print("=" * 66)
    print(f"  ① npm {NPM_PKG:<22} {'已发布 ' + npm_ver if npm_ok else '未发布'}")
    print(f"  ② PR #{PR_NUMBER:<19} {pr_state} / merged={pr_merged} / {pr_status}")
    print(f"  ③ 文章                              需人工确认")
    print()
    print(f"  公开留言 {m.get('public', '?')} · 非站主 {m.get('external', '?')} · "
          f"回复#{SEED_ID} {m.get('replies', '?')}")
    print(f"  访问记录 {m.get('reads', '?')} · 陷阱 {m.get('traps', '?')} · 近24h {m.get('crawled_24h', '?')}")

    unlocked = []
    if npm_ok:
        unlocked.append("npm 已发布")
    if pr_merged:
        unlocked.append("PR 已合并")
    if m.get("external", 0) > 0:
        unlocked.append("出现非站主留言")

    if unlocked:
        print()
        print("  🔔 解锁：" + " / ".join(unlocked))
    else:
        print()
        print("  无变化")

    if not args.no_log:
        line = (f"| {now} | {'已发布 ' + npm_ver if npm_ok else '未发布'} | "
                f"{pr_state}{'/merged' if pr_merged else ''} | "
                f"{m.get('public', '?')} | {m.get('external', '?')} | {m.get('replies', '?')} | "
                f"{m.get('reads', '?')} | {'🔔 ' + '、'.join(unlocked) if unlocked else '—'} |\n")
        try:
            new = not os.path.exists(LOG)
            with open(LOG, "a", encoding="utf-8") as f:
                if new:
                    f.write("# 观测期哨兵日志\n\n")
                    f.write("| 时间 | npm | PR | 留言 | 非站主 | 回复#15 | 访问 | 解锁 |\n")
                    f.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
                f.write(line)
            print(f"  已追加: {os.path.relpath(LOG, ROOT)}")
        except Exception as e:
            print("  写日志失败:", str(e)[:80])

    return 2 if unlocked else 0


if __name__ == "__main__":
    sys.exit(main())
