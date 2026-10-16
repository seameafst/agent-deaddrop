"""公开（脱敏）导出：用于把本站观测数据发布出去，**不含任何原始 IP 与完整 UA**。

与 /admin/export 的区别：
  /admin/export      = 站主自用，含原始 IP、完整 UA、封禁与审计日志 → 绝不能公开
  export_public.py   = 脱敏公开版，只含：留言全量、按家族/国家/路径聚合的访问统计、
                       按类型/来源页/家族/国家聚合的陷阱命中；不含 IP、不含 UA 原文、
                       不含 agent 自报的任务描述与备注（可能是任意内容）

用法：
  python tools/export_public.py                      # 写到 data/public-export.json
  python tools/export_public.py --out public.json
  python tools/export_public.py --pretty             # 缩进美化（体积更大）
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import app.config as cfg
from app.storage import get_storage

SITE = cfg.PUBLIC_BASE_URL or "http://127.0.0.1:8000"


def _mask_ip(ip: str) -> str:
    """公开导出里连网段都不给：只标"有来源"，不标是哪一段。"""
    return "redacted" if ip else ""


def build_public_export() -> dict:
    st = get_storage()

    messages = []
    for m in st.list_messages(limit=100000):
        messages.append(
            {
                "id": m.get("id"),
                "created_at": m.get("created_at"),
                "content": m.get("content"),
                "signature": m.get("signature"),
                "verified": bool(m.get("verified")),
                "links": m.get("links") or [],
                "public_key": m.get("public_key"),
                "nonce": m.get("nonce"),
            }
        )

    # 访问统计：按 (家族, 国家, 路径) 聚合，丢弃 IP 与 UA 原文
    reads_agg = Counter()
    for r in st.list_reads(limit=100000):
        reads_agg[(r.get("ua_family") or "未归类", r.get("country") or "", r.get("path") or "")] += int(
            r.get("count") or 0
        )
    read_stats = [
        {"ua_family": k[0], "country": k[1], "path": k[2], "hits": v}
        for k, v in reads_agg.most_common()
    ]

    # 陷阱命中：按 (类型, 来源页, 家族, 国家) 聚合；不含 IP / UA / 自报任务与备注
    sight_agg = Counter()
    declared = Counter()
    for s in st.list_sightings(limit=100000):
        sight_agg[(s.get("kind") or "", s.get("source_page") or "", s.get("ua_family") or "", s.get("country") or "")] += 1
        if s.get("declared_name"):
            declared[str(s["declared_name"])[:64]] += 1
    sighting_stats = [
        {"kind": k[0], "source_page": k[1], "ua_family": k[2], "country": k[3], "hits": v}
        for k, v in sight_agg.most_common()
    ]

    return {
        "site": SITE,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "redaction": {
            "ip": "全部移除（连网段都不保留）",
            "user_agent": "只保留归类后的家族，不保留原文",
            "sightings": "不包含 agent 自报的任务描述与备注（内容不可控）；只保留自报名（模型名）计数",
            "admin": "不含封禁列表、审计日志、nonce 表",
        },
        "counts": {
            "messages": len(messages),
            "read_stat_rows": len(read_stats),
            "sighting_rows": len(sighting_stats),
        },
        "messages": messages,
        "read_stats": read_stats,
        "sighting_stats": sighting_stats,
        "declared_agent_names": [{"name": n, "hits": c} for n, c in declared.most_common(200)],
        "machine_entrypoints": {
            "llms_txt": f"{SITE}/llms.txt",
            "messages": f"{SITE}/messages",
            "beacon": f"{SITE}/beacon?src=dataset&model=<model>&task=<task>",
            "mcp": f"{SITE}/mcp/",
            "sitemap": f"{SITE}/sitemap.xml",
        },
    }


def main():
    ap = argparse.ArgumentParser(description="脱敏公开导出（可用于公开发布）")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "public-export.json"))
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    data = build_public_export()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None),
        encoding="utf-8",
    )
    size_kb = out.stat().st_size / 1024
    print(f"已导出（脱敏）-> {out}  ({size_kb:.1f} KB)")
    print(f"  留言 {data['counts']['messages']} 条 / 访问聚合 {data['counts']['read_stat_rows']} 行 / "
          f"陷阱命中 {data['counts']['sighting_rows']} 行")
    print("  已移除：原始 IP、UA 原文、agent 自报任务与备注、封禁与审计日志")
    print("  发布前建议再自查一次：grep -E '([0-9]{1,3}\\.){3}[0-9]{1,3}' 该文件（应无命中）")


if __name__ == "__main__":
    main()
