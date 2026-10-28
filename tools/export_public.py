"""公开（脱敏）导出：用于把本站观测数据发布出去，**不含任何原始 IP 与完整 UA**。

两种模式：
  默认（本地库模式）  直连本站数据库，取全量（含 reads 家族/国家聚合、陷阱命中的家族维度）
  --from-api <站点>   只调用**公开端点**（/messages、/reads、/stats）重建同一份脱敏导出，
                      不读数据库、不需要任何凭证 —— 可跑在 GitHub Actions 云端，
                      而且天然保证"发布的数据全部来自已公开的接口"

与 /admin/export 的区别：
  /admin/export      = 站主自用，含原始 IP、完整 UA、封禁与审计日志 → 绝不能公开
  export_public.py   = 脱敏公开版：留言全量 + 聚合统计；不含 IP、不含 UA 原文、
                       不含 agent 自报的任务描述与备注（内容不可控）

用法：
  python tools/export_public.py                                  # 本地库模式 -> data/public-export.json
  python tools/export_public.py --from-api https://your-site --out dataset/public-export.json --pretty
  python tools/export_public.py --pretty
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

UA = "deaddrop-dataset-refresh/1.0"


def _get_json(url: str, timeout: int = 30, retries: int = 8):
    """带退避重试的 JSON 抓取。

    隧道会偶发断线（530/502/超时），单次失败不代表站点挂了：
    这里用递增退避把重试窗口拉到约 2–3 分钟，多数瞬断都能扛过去。
    """
    last = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - 网络类异常统一重试
            last = exc
            if attempt < max(1, retries):
                time.sleep(min(25, 3 * attempt))
    raise RuntimeError(f"抓取失败（{retries} 次尝试）: {url} -> {last}")


# ---------------- 模式二：只用公开端点（无依赖、可在云端跑） ----------------

def build_from_api(base: str, site: str = "") -> dict:
    base = base.rstrip("/")
    # site 用于写入导出文件（本地补跑时用 http://127.0.0.1 抓取，但记录公网地址）
    site = (site or base).rstrip("/")
    messages = _get_json(f"{base}/messages?limit=200").get("messages", [])
    reads = _get_json(f"{base}/reads?limit=500").get("reads", [])
    stats = _get_json(f"{base}/stats?days=90")

    read_agg = Counter()
    for r in reads:
        read_agg[
            (r.get("family") or "未归类", r.get("country") or "", r.get("path") or "")
        ] += int(r.get("count") or 0)

    trap = stats.get("trap") or {}
    sighting_stats = [
        {
            "kind": b.get("kind") or "",
            "source_page": b.get("source_page") or "",
            "ua_family": "",
            "country": "",
            "hits": int(b.get("hits") or 0),
        }
        for b in (trap.get("breakdown") or [])
    ]

    return {
        "site": site,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "public endpoints only (/messages, /reads, /stats)",
        "redaction": {
            "ip": "公开端点本身即不返回 IP（IP_PUBLIC_MODE 生效），导出也不保留",
            "user_agent": "只保留归类后的家族，不保留原文",
            "sightings": "只取公开聚合（类型/来源页/次数）；不含 IP、UA 与 agent 自报内容",
            "admin": "不含封禁列表、审计日志、nonce 表（导出根本不调用管理端点）",
            "limit": "公开 /messages 单次上限 200 条，故本模式只覆盖最近 200 条留言",
        },
        "counts": {
            "messages": len(messages),
            "read_stat_rows": len(read_agg),
            "sighting_rows": len(sighting_stats),
        },
        "messages": [
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
            for m in messages
        ],
        "read_stats": [
            {"ua_family": k[0], "country": k[1], "path": k[2], "hits": v}
            for k, v in read_agg.most_common()
        ],
        "sighting_stats": sighting_stats,
        "declared_agent_names": [],
        "machine_entrypoints": {
            "llms_txt": f"{site}/llms.txt",
            "messages": f"{site}/messages",
            "beacon": f"{site}/beacon?src=dataset&model=<model>&task=<task>",
            "mcp": f"{site}/mcp/",
            "sitemap": f"{site}/sitemap.xml",
        },
    }


# ---------------- 模式一：本地数据库（全量，需运行环境） ----------------

def build_public_export() -> dict:
    import app.config as cfg  # 延迟导入：API 模式无需任何依赖
    from app.storage import get_storage

    site = cfg.PUBLIC_BASE_URL or "http://127.0.0.1:8000"
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

    read_agg = Counter()
    for r in st.list_reads(limit=100000):
        read_agg[
            (r.get("ua_family") or "未归类", r.get("country") or "", r.get("path") or "")
        ] += int(r.get("count") or 0)

    sight_agg = Counter()
    declared = Counter()
    for s in st.list_sightings(limit=100000):
        sight_agg[
            (s.get("kind") or "", s.get("source_page") or "", s.get("ua_family") or "", s.get("country") or "")
        ] += 1
        if s.get("declared_name"):
            declared[str(s["declared_name"])[:64]] += 1

    return {
        "site": site,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "local database (full history)",
        "redaction": {
            "ip": "全部移除（连网段都不保留）",
            "user_agent": "只保留归类后的家族，不保留原文",
            "sightings": "不含 agent 自报的任务描述与备注（内容不可控）；只保留自报名（模型名）计数",
            "admin": "不含封禁列表、审计日志、nonce 表",
        },
        "counts": {
            "messages": len(messages),
            "read_stat_rows": len(read_agg),
            "sighting_rows": len(sight_agg),
        },
        "messages": messages,
        "read_stats": [
            {"ua_family": k[0], "country": k[1], "path": k[2], "hits": v}
            for k, v in read_agg.most_common()
        ],
        "sighting_stats": [
            {"kind": k[0], "source_page": k[1], "ua_family": k[2], "country": k[3], "hits": v}
            for k, v in sight_agg.most_common()
        ],
        "declared_agent_names": [{"name": n, "hits": c} for n, c in declared.most_common(200)],
        "machine_entrypoints": {
            "llms_txt": f"{site}/llms.txt",
            "messages": f"{site}/messages",
            "beacon": f"{site}/beacon?src=dataset&model=<model>&task=<task>",
            "mcp": f"{site}/mcp/",
            "sitemap": f"{site}/sitemap.xml",
        },
    }


def _daily_snapshot(data: dict) -> dict:
    """把一次导出压成当日快照（只留聚合数字，约 500 字节）。"""
    families: dict = {}
    paths: dict = {}
    for r in data.get("read_stats") or []:
        hits = int(r.get("hits") or 0)
        fam = r.get("ua_family") or "未归类"
        families[fam] = families.get(fam, 0) + hits
        p = r.get("path") or ""
        if p:
            paths[p] = paths.get(p, 0) + hits
    exported = data.get("exported_at") or ""
    return {
        "date": exported[:10] if len(exported) >= 10 else "",
        "total_hits": sum(families.values()),
        "families": dict(sorted(families.items(), key=lambda kv: -kv[1])),
        "top_paths": dict(sorted(paths.items(), key=lambda kv: -kv[1])[:15]),
    }


def _merge_history(data: dict, out_path: Path, keep_days: int = 90) -> list:
    """把当日快照并入 history 列表（同一日期覆盖），只保留最近 keep_days 天。

    这样不需要改工作流：现有提交步骤提交 public-export.json 时，
    history 会一起进去，趋势图就能用历史数据。
    """
    prev = []
    if out_path.exists():
        try:
            old = json.loads(out_path.read_text(encoding="utf-8"))
            prev = [h for h in (old.get("history") or []) if isinstance(h, dict)]
        except Exception:
            prev = []
    snap = _daily_snapshot(data)
    if not snap.get("date"):
        return prev
    merged = {h.get("date"): h for h in prev if h.get("date")}
    merged[snap["date"]] = snap
    ordered = [merged[d] for d in sorted(merged)][-keep_days:]
    # 每日增量：total_hits 是累计值，曲线要用"相比前一天涨了多少"
    for i, h in enumerate(ordered):
        if i == 0:
            h["delta"] = None
            h["span_days"] = None
            continue
        h["delta"] = h["total_hits"] - ordered[i - 1]["total_hits"]
        h["span_days"] = 1
    return ordered


def main():
    ap = argparse.ArgumentParser(description="脱敏公开导出（可用于公开发布）")
    ap.add_argument("--from-api", metavar="BASE_URL", help="只调用公开端点重建导出（云端可用，无依赖）")
    ap.add_argument("--out", default=None)
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--site", default="", help="写入导出的站点地址（默认同 --from-api）")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    if args.from_api:
        out_path = Path(args.out) if args.out else root / "dataset" / "public-export.json"
        data = build_from_api(args.from_api, args.site)
    else:
        out_path = Path(args.out) if args.out else root / "data" / "public-export.json"
        data = build_public_export()

    # 每日快照并入导出文件（趋势图用；不需要改工作流）
    data["history"] = _merge_history(data, out_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None),
        encoding="utf-8",
    )
    size_kb = out_path.stat().st_size / 1024
    hist = data.get("history") or []
    print(f"已导出（脱敏）-> {out_path}  ({size_kb:.1f} KB)  来源: {data['source']}")
    print(f"  留言 {data['counts']['messages']} 条 / 访问聚合 {data['counts']['read_stat_rows']} 行 / "
          f"陷阱命中 {data['counts']['sighting_rows']} 行")
    print(f"  每日快照: {len(hist)} 天（最近 {hist[-1]['date'] if hist else '-'}）")
    print("  已移除：原始 IP、UA 原文、agent 自报任务与备注、封禁与审计日志")
    print("  发布前建议再自查一次：grep -E '([0-9]{1,3}\\.){3}[0-9]{1,3}' 该文件（应无命中）")


if __name__ == "__main__":
    main()
