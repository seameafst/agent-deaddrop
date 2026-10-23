#!/usr/bin/env python
"""把当天的脱敏数据集压成一份"每日快照"，供趋势图使用。

输入：dataset/public-export.json（export_public.py 刚导出的）
输出：dataset/history/YYYY-MM-DD.json（体积小，一天一个文件）

快照只保留聚合数字，不含任何逐条访客记录：
  - 当天总命中、各 UA 家族命中、各路径命中、留言数、陷阱数
  - 同一天多次运行会覆盖（以最后一次为准）

用法：
  python tools/snapshot.py
  python tools/snapshot.py --src dataset/public-export.json --out-dir dataset/history
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_snapshot(ds: dict) -> dict:
    read_stats = ds.get("read_stats") or []
    families: dict = {}
    paths: dict = {}
    for r in read_stats:
        hits = int(r.get("hits") or 0)
        fam = r.get("ua_family") or "未归类"
        families[fam] = families.get(fam, 0) + hits
        p = r.get("path") or ""
        if p:
            paths[p] = paths.get(p, 0) + hits

    families = dict(sorted(families.items(), key=lambda kv: -kv[1]))
    paths = dict(sorted(paths.items(), key=lambda kv: -kv[1])[:15])

    exported = ds.get("exported_at") or ""
    day = exported[:10] if len(exported) >= 10 else date.today().isoformat()

    return {
        "date": day,
        "exported_at": exported,
        "site": ds.get("site"),
        "total_hits": sum(families.values()),
        "counts": ds.get("counts") or {},
        "families": families,
        "top_paths": paths,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "dataset" / "public-export.json"))
    ap.add_argument("--out-dir", default=str(ROOT / "dataset" / "history"))
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"找不到数据源: {src}（先跑 tools/export_public.py）")

    ds = json.loads(src.read_text(encoding="utf-8"))
    snap = build_snapshot(ds)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{snap['date']}.json"
    dest.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"  已写入 {dest}")
    print(f"  日期 {snap['date']} · 总命中 {snap['total_hits']} · 家族 {len(snap['families'])} 个 · 路径 {len(snap['top_paths'])} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
