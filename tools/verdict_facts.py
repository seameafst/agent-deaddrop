"""把判定要引用的每个数字，用一条命令打出来。

为什么需要它（2026-11-24）：
    判定草案里的数字散在 SQL、脚本、后台页面里，写完一次就没人复现得了。
    这周还出过一次「MCP 调用 = 0」这种没依据的断言——根子就是没有统一的取证入口。

用法：
    python tools/verdict_facts.py              # Markdown 表格，可直接贴进 results.md
    python tools/verdict_facts.py --json       # 机器可读
    python tools/verdict_facts.py --channels   # 顺带查 npm / PR（会走网络，慢）

只读，不改任何东西。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.config as cfg  # noqa: E402

OPERATOR = "101.71.52.%"
AI_FAMILIES = (
    "Google", "Bing", "Yandex", "Meta", "OpenAI", "Anthropic",
    "Perplexity", "Apple", "Amazon", "SERPstat", "Fossick",
)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(cfg.SQLITE_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def collect() -> dict:
    now = datetime.now(timezone.utc)
    out: dict = {
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_at_local": datetime.now().isoformat(timespec="seconds"),
    }
    c = _conn()
    try:
        q = "SELECT COUNT(*) c FROM messages WHERE channel='public'"
        out["public_messages"] = c.execute(q).fetchone()["c"]

        out["messages"] = [
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "signature": r["signature"],
                "excerpt": (r["content"] or "")[:50],
                "reply_to": r["reply_to"],
            }
            for r in c.execute(
                "SELECT id, created_at, signature, content, reply_to FROM messages "
                "WHERE channel='public' ORDER BY id"
            )
        ]
        out["reply_to_15"] = c.execute("SELECT COUNT(*) c FROM messages WHERE reply_to=15").fetchone()["c"]

        fam = {}
        placeholder = ",".join("?" * len(AI_FAMILIES))
        for r in c.execute(
            f"SELECT ua_family, SUM(count) n, MIN(last_at) f, MAX(last_at) l FROM reads "
            f"WHERE ua_family IN ({placeholder}) AND ip NOT LIKE ? GROUP BY ua_family ORDER BY n DESC",
            (*AI_FAMILIES, OPERATOR),
        ):
            fam[r["ua_family"]] = {"hits": r["n"], "first": (r["f"] or "")[:10], "last": (r["l"] or "")[:10]}
        out["families"] = fam

        out["ai_hits"] = sum(v["hits"] for v in fam.values())
        out["total_hits"] = c.execute(
            "SELECT COALESCE(SUM(count),0) c FROM reads WHERE ip NOT LIKE ?", (OPERATOR,)
        ).fetchone()["c"]

        g = fam.get("Google") or {}
        out["google_last"] = g.get("last", "")
        if out["google_last"]:
            try:
                d = datetime.strptime(out["google_last"], "%Y-%m-%d").date()
                out["days_since_google"] = (now.date() - d).days
            except Exception:
                out["days_since_google"] = None
        out["google_since_1116"] = c.execute(
            "SELECT COALESCE(SUM(count),0) c FROM reads WHERE ua_family='Google' AND last_at >= '2026-11-16'"
        ).fetchone()["c"]

        out["trap_hits"] = c.execute("SELECT COUNT(*) c FROM sightings").fetchone()["c"]
        out["trap_top_asn"] = [
            {"asn": r["asn"], "hits": r["n"]}
            for r in c.execute(
                "SELECT asn, COUNT(*) n FROM sightings WHERE asn IS NOT NULL AND asn != '' "
                "GROUP BY asn ORDER BY n DESC LIMIT 3"
            )
        ]
    finally:
        c.close()

    try:
        from app import mcp_stats

        s = mcp_stats.summary()
        out["mcp"] = {
            "total": s.get("total", 0),
            "selftest": s.get("selftest_total", 0),
            "external": s.get("external_total", 0),
            "by_tool": s.get("by_tool", {}),
            "first_recorded_at": s.get("first_recorded_at", ""),
        }
    except Exception as e:
        out["mcp"] = {"error": str(e)[:100]}

    return out


def check_channels(out: dict) -> None:
    """npm / PR 状态。网络不好时如实记 unreachable，不猜。"""
    ch: dict = {}
    try:
        import urllib.request

        req = urllib.request.Request(
            "https://registry.npmjs.org/agent-deaddrop-mcp",
            headers={"User-Agent": "verdict-facts/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        ch["npm"] = {"published": True, "latest": (data.get("dist-tags") or {}).get("latest", "")}
    except Exception as e:
        code = getattr(e, "code", None)
        ch["npm"] = {"published": False if code == 404 else None, "detail": f"HTTP {code}" if code else str(e)[:80]}

    try:
        tok = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
        import urllib.request

        req = urllib.request.Request(
            "https://api.github.com/repos/punkpeye/awesome-remote-mcp-servers/pulls/2493",
            headers={"Authorization": "Bearer " + tok, "User-Agent": "verdict-facts/1.0"},
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode())
        ch["pr_2493"] = {
            "state": d.get("state"),
            "merged": bool(d.get("merged")),
            "mergeable_state": d.get("mergeable_state"),
            "updated_at": d.get("updated_at"),
        }
    except Exception as e:
        ch["pr_2493"] = {"state": "unreachable", "detail": str(e)[:80]}

    out["channels"] = ch


def render_md(d: dict) -> str:
    L = []
    L.append(f"<!-- verdict facts @ {d['generated_at_local']} -->")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("| --- | --- |")
    L.append(f"| 生成时间 | {d['generated_at_local']} |")
    L.append(f"| 公开留言 | {d['public_messages']} 条 |")
    L.append(f"| `reply_to=15` 回复 | {d['reply_to_15']} |")
    L.append(f"| AI 家族命中 / 总命中 | {d['ai_hits']} / {d['total_hits']} = "
             f"{100.0 * d['ai_hits'] / max(1, d['total_hits']):.1f}% |")
    L.append(f"| Google 最后出现 | {d['google_last'] or '（无）'} "
             f"（{d['days_since_google']} 天前） |")
    L.append(f"| Google 11-16 之后 | **{d['google_since_1116']} 次** |")
    L.append(f"| 陷阱命中 | {d['trap_hits']} 次 |")
    m = d.get("mcp") or {}
    L.append(f"| MCP 调用 | total={m.get('total')} / selftest={m.get('selftest')} / "
             f"**external={m.get('external')}** |")
    L.append(f"| MCP 首次记录 | {m.get('first_recorded_at') or '（无）'} |")
    L.append("")
    L.append("**家族明细**")
    L.append("")
    L.append("| 家族 | 命中 | 首次 | 最后 |")
    L.append("| --- | --- | --- | --- |")
    for f, v in d["families"].items():
        L.append(f"| {f} | {v['hits']} | {v['first']} | {v['last']} |")
    L.append("")
    L.append("**留言来源**")
    L.append("")
    for msg in d["messages"]:
        L.append(f"- #{msg['id']} {msg['created_at'][:16]} `{msg['signature']}` — {msg['excerpt']}")
    if d.get("channels"):
        L.append("")
        L.append("**外部通道**")
        L.append("")
        for k, v in d["channels"].items():
            L.append(f"- {k}: `{json.dumps(v, ensure_ascii=False)}`")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--channels", action="store_true")
    args = ap.parse_args()

    d = collect()
    if args.channels:
        check_channels(d)

    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(render_md(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
