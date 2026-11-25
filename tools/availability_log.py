"""记录公网可用性的状态变化（不是每次探测都写）。

为什么需要（2026-11-25）：
    那天 21:18–21:45 站点公网断了半小时多。事后我要写判定，只能翻 watchdog.log
    猜时间段——而且那里面混着"重启失败"的记录，不是纯粹的可用性证据。

    判定要求「写明断线窗口」，所以我需要一个精确、可复查的时间线：
    状态只在 通→断 / 断→通 时落一行，数据量极小。

用法：
    python tools/availability_log.py            # 探一次，状态变了就记一行
    python tools/availability_log.py --summary  # 打印所有断线窗口
    python tools/availability_log.py --base https://wirehush.com
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "data" / "public-availability.jsonl"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def probe(base: str) -> tuple[bool, str]:
    req = urllib.request.Request(
        base.rstrip("/") + "/health", headers={"User-Agent": "availability-probe/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(200).decode("utf-8", "replace")
            return (r.status == 200, f"HTTP {r.status} {body[:40]}")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:80]


def probe_confirm(base: str, attempts: int = 3) -> tuple[bool, str]:
    """连续失败才算断。

    单次请求会抽风：2026-11-25 22:00 我手动探了一次 `000`，十几秒后再探就是 200。
    如果不重试，这种抖动会被写进「断线窗口」，把判定用的停机时长弄脏。
    """
    last = ""
    for i in range(max(1, attempts)):
        up, detail = probe(base)
        if up:
            return True, detail
        last = detail
        if i < attempts - 1:
            time.sleep(5)
    return False, last


def _last_state() -> tuple[bool | None, str]:
    if not STATE_FILE.exists():
        return None, ""
    last = None
    for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                last = json.loads(line)
            except Exception:
                continue
    if not last:
        return None, ""
    return bool(last.get("up")), last.get("at", "")


def record(up: bool, detail: str) -> bool:
    prev_up, _prev_at = _last_state()
    if prev_up is not None and prev_up == up:
        return False
    row = {"at": _now(), "up": up, "detail": detail}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"  记录状态变化: {'UP' if up else 'DOWN'} @ {row['at']} ({detail})")
    return True


def summary() -> int:
    if not STATE_FILE.exists():
        print("  没有可用性记录")
        return 0
    rows = []
    for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    if not rows:
        print("  没有可用性记录")
        return 0

    print("  状态变化时间线：")
    for r in rows:
        print(f"    {r['at']}  {'UP  ' if r.get('up') else 'DOWN'}  {r.get('detail','')}")

    total_down = 0.0
    print("\n  断线窗口（成对的 DOWN → UP）：")
    down_at = None
    for r in rows:
        t = datetime.fromisoformat(r["at"])
        if not r.get("up") and down_at is None:
            down_at = t
        elif r.get("up") and down_at is not None:
            mins = (t - down_at).total_seconds() / 60
            total_down += mins
            print(f"    {down_at.isoformat(timespec='seconds')} → {r['at']}  （{mins:.0f} 分钟）")
            down_at = None
    if down_at is not None:
        print(f"    {down_at.isoformat(timespec='seconds')} → 至今（仍在断）")
    print(f"\n  累计断线: {total_down:.0f} 分钟")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://wirehush.com")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="只探测不写日志（负向测试用）")
    args = ap.parse_args()

    if args.summary:
        return summary()

    up, detail = probe_confirm(args.base)
    print(f"  探测 {args.base}/health -> {'UP' if up else 'DOWN'}（{detail}）")
    if args.dry_run:
        print("  --dry-run：不写日志")
    else:
        record(up, detail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
