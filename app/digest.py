"""每日观测日报：把过去 24 小时的关键变化汇总成一段可读文本。

数据源全部来自本地库（不走网络），因此即使公网抖动也能生成；
每日快照部分会顺带读一次远端数据集（失败则忽略）。

注意：默认排除站主自己的访问（管理 IP + 本机），否则日报会被自己的验证请求污染。
"""
import ipaddress
from datetime import datetime, timedelta, timezone
from typing import List

from app import botverify
from app import config as cfg
from app.storage import get_storage
from app.ua import AI_FAMILIES


def _self_networks():
    nets = []
    for item in getattr(cfg, "ADMIN_ALLOWED_IPS", []) or []:
        try:
            nets.append(ipaddress.ip_network(item, strict=False))
        except Exception:
            continue
    for loop in ("127.0.0.1/32", "::1/128"):
        try:
            nets.append(ipaddress.ip_network(loop, strict=False))
        except Exception:
            pass
    return nets


def _is_self(ip: str, nets) -> bool:
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except Exception:
        return False
    return any(addr in n for n in nets if n.version == addr.version)


def _top(items, key="hits", limit=5):
    return sorted(items or [], key=lambda x: -(x.get(key) or 0))[:limit]


def build(hours: int = 24, include_self: bool = False) -> dict:
    hours = max(1, min(int(hours), 24 * 30))
    st = get_storage()
    reads = st.list_reads(limit=5000)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cut_s = cutoff.isoformat(timespec="seconds")
    nets = _self_networks()

    recent = [r for r in reads if (r.get("last_at") or "") >= cut_s]
    excluded = 0
    if not include_self:
        kept = []
        for r in recent:
            if _is_self(r.get("ip") or "", nets):
                excluded += 1
            else:
                kept.append(r)
        recent = kept

    fam: dict = {}
    for r in recent:
        f = r.get("ua_family") or "未归类"
        fam[f] = fam.get(f, 0) + int(r.get("count") or 0)
    families = [{"family": k, "hits": v} for k, v in fam.items()]
    families.sort(key=lambda x: -x["hits"])

    ai_rows = [x for x in families if x["family"] in AI_FAMILIES]

    sightings = [
        s for s in st.list_sightings(limit=200)
        if (s.get("at") or "") >= cut_s and (include_self or not _is_self(s.get("ip") or "", nets))
    ]
    messages = [m for m in st.list_messages(limit=100, channel="public") if (m.get("created_at") or "") >= cut_s]
    annex = [m for m in st.list_messages(limit=50, channel="annex") if (m.get("created_at") or "") >= cut_s]

    bait = {}
    for r in recent:
        p = r.get("path") or ""
        if p in ("/collab", "/relay", "/signal", "/scratchpad", "/answers", "/bulletin", "/beacon"):
            bait[p] = bait.get(p, 0) + int(r.get("count") or 0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hours": hours,
        "excluded_self_rows": excluded,
        "total_hits": sum(x["hits"] for x in families),
        "families": _top(families, limit=8),
        "ai_families": ai_rows,
        "sightings": [
            {
                "at": s.get("at"),
                "source_page": s.get("source_page"),
                "family": s.get("ua_family"),
                "country": s.get("country"),
                "verdict": botverify.verdict_text(s.get("ua_family") or "", s.get("asn") or ""),
            }
            for s in sightings[:20]
        ],
        "new_public_messages": len(messages),
        "new_annex_messages": len(annex),
        "bait_hits": sorted(bait.items(), key=lambda kv: -kv[1])[:6],
    }


def render_markdown(d: dict) -> str:
    lines: List[str] = []
    lines.append(f"# 观测日报 · {d['generated_at'][:16].replace('T', ' ')} UTC")
    lines.append("")
    lines.append(f"窗口：最近 {d['hours']} 小时 · 总命中 {d['total_hits']}")
    lines.append("")
    lines.append("## 访客家族（Top 8）")
    if d["families"]:
        for f in d["families"]:
            star = " ⭐" if f["family"] in AI_FAMILIES else ""
            lines.append(f"- {f['family']}: {f['hits']} 次{star}")
    else:
        lines.append("- （窗口内没有访问记录）")

    lines.append("")
    lines.append("## AI / 搜索引擎家族")
    if d["ai_families"]:
        for f in d["ai_families"]:
            lines.append(f"- {f['family']}: {f['hits']} 次")
    else:
        lines.append("- （窗口内没有 AI/搜索引擎爬虫）")

    lines.append("")
    lines.append(f"## 陷阱命中（{len(d['sightings'])} 条）")
    if d["sightings"]:
        for s in d["sightings"][:10]:
            verdict = f" · {s['verdict']}" if s["verdict"] else ""
            lines.append(f"- {s['at'][:19]} {s['source_page']} {(s['family'] or '-')} "
                         f"{(s['country'] or '-')}{verdict}")
    else:
        lines.append("- （无）")

    lines.append("")
    lines.append("## 诱饵页命中")
    if d["bait_hits"]:
        for p, n in d["bait_hits"]:
            lines.append(f"- {p}: {n} 次")
    else:
        lines.append("- （无）")

    lines.append("")
    lines.append(f"## 新留言：公开 {d['new_public_messages']} 条 · annex {d['new_annex_messages']} 条")
    lines.append("")
    lines.append("## 关注点")
    if d["ai_families"]:
        lines.append("- 有 AI/搜索引擎爬虫到访，注意它在抓哪些路径（/admin/crawler-paths）")
    else:
        lines.append("- 窗口内没有 AI/搜索引擎爬虫，可考虑补外链或更新内容")
    if d["sightings"]:
        lines.append("- 陷阱有命中，检查 /admin/bait-stats 看哪个诱饵有效")
    lines.append("")
    return "\n".join(lines)
