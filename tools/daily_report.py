#!/usr/bin/env python
"""生成每日观测日报并写入 data/reports/YYYY-MM-DD.md。

用法：
  python tools\\daily_report.py             # 默认 24 小时窗口
  python tools\\daily_report.py --hours 72  # 自定义窗口
  python tools\\daily_report.py --print     # 同时打印到终端

由计划任务每天 09:00 触发（见 tools/install_daily_report.ps1）。
日报内容不含站主自己的访问记录。
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import digest  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--out-dir", default=str(ROOT / "data" / "reports"))
    ap.add_argument("--print", dest="show", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    d = digest.build(hours=args.hours)
    text = digest.render_markdown(d)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    dest = out_dir / f"{today}.md"
    dest.write_text(text, encoding="utf-8")

    print(f"  日报已写入 {dest}")
    print(f"  窗口 {d['hours']}h · 总命中 {d['total_hits']} · "
          f"AI 家族 {len(d['ai_families'])} 个 · 陷阱命中 {len(d['sightings'])} 条")
    if args.show:
        print()
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
