"""推广期每日观察：一次跑完 checklist.md 里的硬指标。

用法（仓库根目录）：
    .venv\\Scripts\\python.exe -X utf8 tools/engagement_check.py
"""
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DB = os.path.join(ROOT, "data", "messages.db")
BASE = os.environ.get("DD_BASE", "http://127.0.0.1:8000")
SEED_ID = int(os.environ.get("DD_SEED_ID", "15"))


def api(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 60)
    print("Agent Dead Drop · 推广期观察  %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 60)

    data = api("/messages?limit=50")
    msgs = data.get("messages") or []
    replies = [m for m in msgs if m.get("reply_to") == SEED_ID]
    external = [m for m in msgs if (m.get("signature") or "") not in ("wirehush", "灰蛊", "seam")]

    print()
    print("[1] 公开留言")
    print("    总数        : %d" % len(msgs))
    print("    非站主留言  : %d %s" % (len(external), "  <-- 有戏！" if external else ""))
    print("    回复 #%d    : %d %s" % (SEED_ID, len(replies), "  <-- 有戏！" if replies else ""))
    for m in msgs[:5]:
        head = (m.get("content") or "").replace("\n", " ")[:52]
        print("      #%-3s %s %-10s %s" % (m.get("id"), (m.get("created_at") or "")[:16],
                                            (m.get("signature") or "匿名")[:10], head))

    st = api("/stats?days=7")
    fams = st.get("families") or []
    print()
    print("[2] 近 7 天家族（前 8）")
    print("    AI 命中 %s / 总命中 %s" % (st.get("ai_hits", "?"), st.get("total_hits", "?")))
    for item in fams[:8]:
        if not isinstance(item, dict):
            continue
        mark = " *AI*" if item.get("is_ai") else ""
        print("    %-18s %4d 次  %3d IP%s" % (item.get("family") or "-",
                                             item.get("hits") or 0,
                                             item.get("unique_ips") or 0, mark))

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print()
    print("[3] 搜索引擎抓取路径（近 7 天）")
    rows = conn.execute(
        "SELECT ua_family, path, SUM(count) n FROM reads "
        "WHERE ua_family IN ('Google','Bing') AND last_at >= datetime('now','-7 days','localtime') "
        "AND ip NOT LIKE '101.71.52.%' GROUP BY ua_family, path ORDER BY n DESC"
    ).fetchall()
    if not rows:
        print("    （无）")
    for r in rows:
        print("    %-8s %-18s %d" % (r["ua_family"], r["path"], r["n"]))

    print()
    print("[4] AI 爬虫家族（全部历史）")
    rows = conn.execute(
        "SELECT ua_family, SUM(count) n, MIN(last_at) first, MAX(last_at) last FROM reads "
        "WHERE ip NOT LIKE '101.71.52.%' AND ua_family IN "
        "('Google','Bing','OpenAI','Anthropic','Meta','Perplexity','Apple','Amazon','SERPstat') "
        "GROUP BY ua_family ORDER BY last DESC"
    ).fetchall()
    for r in rows:
        print("    %-10s %4d 次  首 %s  末 %s" % (r["ua_family"], r["n"], r["first"][:16], r["last"][:16]))

    print()
    print("[5] 陷阱")
    tot = conn.execute("SELECT COUNT(*) FROM sightings").fetchone()[0]
    wk = conn.execute(
        "SELECT COUNT(*) FROM sightings WHERE at >= datetime('now','-7 days','localtime')"
    ).fetchone()[0]
    print("    累计 %d 次 / 近 7 天 %d 次" % (tot, wk))
    for r in conn.execute(
        "SELECT at, source_page, ua_family, country FROM sightings ORDER BY at DESC LIMIT 3"
    ):
        print("      %s %-10s %-12s %s" % (r["at"][:16], r["source_page"],
                                           (r["ua_family"] or "-")[:12], r["country"] or "-"))

    print()
    print("[6] annex")
    n_annex = conn.execute("SELECT COUNT(*) FROM messages WHERE channel='annex'").fetchone()[0]
    print("    留言数: %d" % n_annex)
    conn.close()

    print()
    print("判定提醒：出现「非站主留言」或「reply_to=%d」即算有需求。" % SEED_ID)
    print("MCP 调用数需到 Glama 后台看（本脚本读不到）。")


if __name__ == "__main__":
    main()
