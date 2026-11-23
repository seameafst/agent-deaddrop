"""数据集新鲜度守卫。

背景（2026-11-23 实测）：
    workflow 声明 cron 是 03:23 UTC，但实际运行时间在 11:17–11:36 UTC 之间浮动
    （GitHub 免费 runner 的 schedule 延迟，官方文档承认会有延迟甚至跳过）。
    11-23 当天到 12:06 UTC 还没有运行，公网数据集比本地落后约 24 小时。

做法：
    读仓库里那份 dataset/public-export.json 的 exported_at，
    超过阈值就用 gh 手动触发 workflow_dispatch（不需要额外权限，repo scope 够用）。

用法：
    python tools/dataset_guard.py                # 阈值默认 30 小时
    python tools/dataset_guard.py --max-age 20   # 自定义
    python tools/dataset_guard.py --check-only   # 只报告不触发

退出码：
    0 = 新鲜，或已触发（不需要再处理）
    2 = 触发失败（需要人看）
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "dataset" / "public-export.json"
WORKFLOW = "refresh-dataset.yml"


def _age_hours(ts: str) -> float:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        return 1e9


def remote_exported_at() -> str:
    """仓库里那份数据集的 exported_at；拿不到返回空串。"""
    try:
        out = subprocess.run(
            ["gh", "api", "repos/seameafst/agent-deaddrop/contents/dataset/public-export.json",
             "-H", "Accept: application/vnd.github.raw"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if out.returncode != 0:
            return ""
        return json.loads(out.stdout).get("exported_at", "") or ""
    except Exception:
        return ""


def local_exported_at() -> str:
    try:
        return json.loads(LOCAL.read_text(encoding="utf-8")).get("exported_at", "") or ""
    except Exception:
        return ""


def trigger() -> tuple[bool, str]:
    try:
        out = subprocess.run(
            ["gh", "workflow", "run", WORKFLOW, "--ref", "main"],
            capture_output=True, text=True, timeout=90, check=False,
        )
        msg = (out.stdout or out.stderr or "").strip().splitlines()
        return out.returncode == 0, (msg[0] if msg else "")
    except Exception as e:
        return False, str(e)[:120]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age", type=float, default=30.0, help="允许的最大滞后小时数")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    remote = remote_exported_at()
    local = local_exported_at()

    print(f"  仓库数据集 exported_at: {remote or '(读取失败)'}")
    print(f"  本地数据集 exported_at: {local or '(读取失败)'}")

    if not remote:
        print("  结论: 读不到仓库数据集（gh 或网络问题），本轮不处理")
        return 0

    age = _age_hours(remote)
    print(f"  滞后: {age:.1f} 小时（阈值 {args.max_age:.0f}h）")

    if age <= args.max_age:
        print("  结论: 新鲜，无需动作")
        return 0

    if args.check_only:
        print("  结论: 已过期（--check-only，未触发）")
        return 0

    ok, msg = trigger()
    if ok:
        print("  结论: 已触发 workflow_dispatch" + (f"（{msg}）" if msg else ""))
        return 0
    print(f"  结论: 触发失败 — {msg}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
