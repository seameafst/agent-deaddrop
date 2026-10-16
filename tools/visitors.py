"""查看原始访客记录（只有站主能看：自动读取 .env 里的 ADMIN_TOKEN + TOTP）。

用法：
  python tools/visitors.py                    # 最近 30 条原始访客（走管理 API）
  python tools/visitors.py --limit 200
  python tools/visitors.py --summary          # 按国家 / UA 家族汇总
  python tools/visitors.py --export out.json  # 导出全量（含原始 IP、UA、封禁、审计日志）
  python tools/visitors.py --local            # 直连数据库读（不经过 HTTP，不需要令牌）
  python tools/visitors.py --no-ua            # 不显示 UA（只看 IP / 归属 / 路径）
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import app.config as cfg
from app.totp import code as totp_code

BASE = (cfg.PUBLIC_BASE_URL or "http://127.0.0.1:8000").rstrip("/")


def admin_headers() -> dict:
    if not cfg.ADMIN_TOKEN:
        sys.exit("未配置 ADMIN_TOKEN（在 .env 里设置后才能通过 API 查看）")
    headers = {"X-Admin-Token": cfg.ADMIN_TOKEN, "User-Agent": "deaddrop-visitors/1.0"}
    if cfg.ADMIN_TOTP_SECRET:
        headers["X-Admin-TOTP"] = totp_code(cfg.ADMIN_TOTP_SECRET)
    return headers


def api_get(path: str, headers: dict):
    req = urllib.request.Request(BASE + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200]
        sys.exit(f"请求 {path} 失败：HTTP {e.code} {detail}")


def local_reads(limit: int):
    """直连数据库（本机文件），不需要令牌。"""
    import sqlite3

    conn = sqlite3.connect(cfg.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT path, ip, user_agent, ua_family, country, asn, day, count, first_at, last_at"
        " FROM reads ORDER BY last_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def print_table(rows, show_ua=True):
    if not rows:
        print("（暂无访客记录）")
        return
    print(f"{'最后访问':19s} {'来源 IP':22s} {'国家':4s} {'家族':10s} {'次数':>4s}  {'路径'}")
    print("-" * 100)
    for r in rows:
        ip = str(r.get("ip") or "")
        cc = (r.get("country") or "-").ljust(4)
        fam = (r.get("ua_family") or r.get("family") or "-")
        ts = (r.get("last_at") or "")[:19].replace("T", " ")
        print(f"{ts:19s} {ip:22s} {cc:4s} {fam:10s} {int(r.get('count') or 0):>4d}  {r.get('path')}")
        if show_ua and r.get("user_agent"):
            asn = r.get("asn") or ""
            print(f"{'':19s} └─ UA: {str(r['user_agent'])[:80]}{('  [' + asn + ']') if asn else ''}")


def main():
    ap = argparse.ArgumentParser(description="查看原始访客记录（站主专用）")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--summary", action="store_true", help="按国家 / UA 家族汇总")
    ap.add_argument("--export", metavar="FILE", help="导出全量 JSON（含原始 IP）")
    ap.add_argument("--local", action="store_true", help="直连数据库读取（不经 HTTP）")
    ap.add_argument("--no-ua", action="store_true", help="不显示 UA 明细")
    args = ap.parse_args()

    if args.export:
        data = api_get("/admin/export", admin_headers())
        Path(args.export).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已导出到 {args.export}")
        print(f"  留言 {len(data.get('messages', []))} 条 / 访客 {len(data.get('reads', []))} 条 / "
              f"封禁 {len(data.get('bans', []))} 条 / 审计 {len(data.get('admin_log', []))} 条")
        return

    if args.local:
        rows = local_reads(args.limit)
        src = "本地数据库"
    else:
        rows = api_get(f"/admin/reads?limit={max(1, min(args.limit, 2000))}", admin_headers())["reads"]
        src = f"管理 API（{BASE}）"

    print(f"\n=== 原始访客记录 · {src} · 最近 {len(rows)} 条 ===\n")
    print_table(rows, show_ua=not args.no_ua)

    if args.summary and rows:
        print("\n=== 汇总 ===")
        by_cc = Counter((r.get("country") or "未知") for r in rows)
        by_fam = Counter((r.get("ua_family") or r.get("family") or "未知") for r in rows)
        print("  国家/地区:", ", ".join(f"{k}×{v}" for k, v in by_cc.most_common(10)))
        print("  UA 家族  :", ", ".join(f"{k}×{v}" for k, v in by_fam.most_common(10)))
        uniq = {str(r.get("ip")) for r in rows if r.get("ip")}
        print(f"  独立 IP  : {len(uniq)} 个")
    print()


if __name__ == "__main__":
    main()
