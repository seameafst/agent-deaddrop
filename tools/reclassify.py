#!/usr/bin/env python
"""按当前 UA 规则重新归类历史记录（reads / sightings 的 ua_family）。

场景：新增/修改了 app/ua.py 的家族规则后，旧记录仍保留插入时的分类，
      跑一次本脚本即可让管理台的历史数据与新规则一致。

用法：
  python tools\\reclassify.py            # 直接执行
  python tools\\reclassify.py --dry-run  # 只看会改多少行
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ua import classify  # noqa: E402

DB = ROOT / "data" / "messages.db"
TABLES = ("reads", "sightings")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    conn = sqlite3.connect(args.db)
    total_changed = 0
    for table in TABLES:
        rows = conn.execute(f"SELECT DISTINCT user_agent FROM {table}").fetchall()
        changed = 0
        for (user_agent,) in rows:
            old = conn.execute(
                f"SELECT DISTINCT ua_family FROM {table} WHERE user_agent=?", (user_agent,)
            ).fetchall()
            new_fam = classify(user_agent or "")
            for (old_fam,) in old:
                if (old_fam or "") == new_fam:
                    continue
                changed += conn.execute(
                    f"UPDATE {table} SET ua_family=? WHERE user_agent=? AND ua_family IS ?",
                    (new_fam, user_agent, old_fam),
                ).rowcount
        print(f"  {table}: 扫描 {len(rows)} 种 UA，更新 {changed} 行")
        total_changed += changed

    if args.dry_run:
        conn.rollback()
        print(f"  [dry-run] 共 {total_changed} 行会变化（未提交）")
    else:
        conn.commit()
        print(f"  已提交，共更新 {total_changed} 行")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
