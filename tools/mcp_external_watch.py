"""盯住「外部 tools/call」——判定里真正算数的那一件事。

为什么单独做一个（2026-11-25）：
    Glama 已经连续三次 `initialize` 握手（10:54 / 11:56 / 12:59 UTC），但**零 tools/call**。
    握手只说明"连得上"，`tools/call` 才说明"真的在用"。
    这个数字决定 11-27 的判定走向，所以要有人专门盯，而不是靠我下次想起来再查。

做法：
    统计「非 selftest 的 tools/call」条数，与上次记录比较；只在增加时报警（退出码 2），
    并把新出现的行打印出来（工具名 + 时间 + 客户端）。

用法：
    python tools/mcp_external_watch.py            # 查一次，有新增则 exit 2
    python tools/mcp_external_watch.py --json     # 机器可读
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.config as cfg  # noqa: E402

STATE = ROOT / "data" / ".mcp-external-state.json"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(cfg.SQLITE_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def collect() -> dict:
    c = _conn()
    try:
        rows = list(c.execute(
            "SELECT id, at, tool, client FROM mcp_calls "
            "WHERE method='tools/call' AND COALESCE(selftest,0)=0 ORDER BY id"
        ))
        init_rows = list(c.execute(
            "SELECT id, at, client FROM mcp_calls "
            "WHERE method='initialize' AND COALESCE(selftest,0)=0 ORDER BY id"
        ))
        rejected_rows = list(c.execute(
            "SELECT id, at, method, client FROM mcp_calls "
            "WHERE method LIKE '%:rejected' AND COALESCE(selftest,0)=0 ORDER BY id"
        ))
        return {
            "external_tools_calls": len(rows),
            "rows": [dict(r) for r in rows],
            "external_initializes": len(init_rows),
            "external_rejected": len(rejected_rows),
            "rejected_rows": [dict(r) for r in rejected_rows],
            "last_initialize": (dict(init_rows[-1]) if init_rows else None),
            "max_id": (rows[-1]["id"] if rows else 0),
        }
    finally:
        c.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-state", action="store_true", help="不写状态文件（负向测试用）")
    args = ap.parse_args()

    data = collect()
    prev = {}
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    prev_calls = int(prev.get("external_tools_calls", 0))
    prev_init = int(prev.get("external_initializes", 0))

    if args.json:
        print(json.dumps({**data, "previous": prev}, ensure_ascii=False, indent=2))
    else:
        print(f"  外部 tools/call: {data['external_tools_calls']}（上次 {prev_calls}）")
        print(f"  外部 initialize: {data['external_initializes']}（上次 {prev_init}）")
        print(f"  外部被拒(4xx): {data['external_rejected']}（上次 {prev.get('external_rejected', 0)}）")
        li = data.get("last_initialize")
        if li:
            print(f"  最后一次外部握手: {li['at']} by {li['client'] or '(未命名)'}")

    prev_rej = int(prev.get("external_rejected", 0))
    rejected_up = data["external_rejected"] > prev_rej
    if rejected_up:
        print("\n  ⚠️ 外部探测被 4xx 拒了，说明它在试我们没支持的形态：")
        for r in data["rejected_rows"][prev_rej:]:
            print(f"     #{r['id']} {r['at']} {r['method']} client={r['client'] or '(未命名)'}")

    changed = data["external_tools_calls"] > prev_calls
    if changed:
        new_rows = data["rows"][prev_calls:]
        print("\n  🔔 外部 tools/call 增加了：")
        for r in new_rows:
            print(f"     #{r['id']} {r['at']}  tool={r['tool']}  client={r['client'] or '(未命名)'}")

    if args.no_state:
        print("  --no-state：不写状态文件")
        return 0 if not changed else 2
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(
        json.dumps(
            {
                "external_tools_calls": data["external_tools_calls"],
                "external_initializes": data["external_initializes"],
                "external_rejected": data["external_rejected"],
                "checked_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return 2 if (changed or rejected_up) else 0


if __name__ == "__main__":
    sys.exit(main())
