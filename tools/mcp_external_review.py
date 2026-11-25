"""判定前的人工复核表：把所有「非 selftest」的 MCP 记录列出来，逐条过。

为什么要单独一个脚本（2026-11-25）：
    计数器的自测判定有已知弱点（靠命名约定 + 是否带 CF 头），
    所以 `external_total` 不能直接采信。判定前必须逐条看。
    而写一个「贴进 PowerShell 的 SQL 一行流」我被引号坑了两次——
    脚本化的好处是：命令可以原样复制，不用本地转义。

用法：
    python tools/mcp_external_review.py
    python tools/mcp_external_review.py --all     # 连 selftest 一起看
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.config as cfg  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="包含 selftest 记录")
    args = ap.parse_args()

    conn = sqlite3.connect(cfg.SQLITE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    where = "" if args.all else "WHERE COALESCE(selftest,0)=0"
    rows = list(
        conn.execute(
            f"SELECT id, at, method, tool, client, via_edge, selftest "
            f"FROM mcp_calls {where} ORDER BY id"
        )
    )
    total = conn.execute("SELECT COUNT(*) c FROM mcp_calls").fetchone()["c"]
    conn.close()

    print(f"  全表 {total} 行；下表 {'全部' if args.all else '只含非 selftest'} {len(rows)} 行\n")

    if not rows:
        print("  没有需要复核的记录（全部标为 selftest）")
        return 0

    hdr = f"  {'#':>4}  {'时间(UTC)':<19}  {'method':<20} {'tool':<16} {'client':<24} edge self"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in rows:
        print(
            f"  {r['id']:>4}  {r['at'][:19]:<19}  {r['method']:<20} "
            f"{(r['tool'] or '-'):<16} {(r['client'] or '(空)'):<24} "
            f"{r['via_edge']!s:<4} {r['selftest']}"
        )

    print("\n  复核要点：")
    print("    1. 时间是否落在我做测试的时段？（对照 results.md 当天记录）")
    print("    2. client 是不是我起的名字？（我的测试名都含 selftest）")
    print("    3. via_edge=1 表示经 Cloudflare 进来，=0 是本机直连")
    print("    手工把每行标成「外部真实」或「我的测试」，以手算结果为准。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
