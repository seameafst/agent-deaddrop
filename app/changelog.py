"""从 git 历史生成站点变更记录（/bulletin 用），以及页面"最后更新"日期。

降级策略：
  - 没有 .git（如精简 Docker 镜像）→ 返回空，页面回退到人工维护的静态记录；
  - 本地 git 落后太久（>14 天）→ 视为不可信，同样返回空；
  - 结果缓存 5 分钟，避免每次请求都跑 git。
"""
import subprocess
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
STALE_DAYS = 14
_cache = {"at": 0.0, "data": None}


def _git(*args, timeout: int = 10):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def available() -> bool:
    try:
        return (ROOT / ".git").exists()
    except Exception:
        return False


def page_updated_at() -> str:
    """页面内容最后一次更新的日期（YYYY-MM-DD）。git 不可用时用文件修改时间。

    看的是一组"内容文件"，不是单个 trap.py：
    参考页的正文会随 agents_page.py / wall.py / main.py 的改动一起变，
    只盯 trap.py 会让页面上的"最后更新"永远停在旧日期——对爬虫是错误的新鲜度信号。
    """
    content_files = ["app/trap.py", "app/agents_page.py", "app/wall.py", "app/main.py"]
    best = ""
    try:
        out = _git("log", "-1", "--date=short", "--pretty=format:%ad", "--", *content_files)
        if out.returncode == 0:
            text = out.stdout.strip().splitlines()
            if text and text[0]:
                best = text[0].strip()
    except Exception:
        pass
    if best:
        return best
    try:
        newest = None
        for rel in content_files:
            target = ROOT / rel
            if target.exists():
                mt = target.stat().st_mtime
                if newest is None or mt > newest:
                    newest = mt
        if newest is not None:
            return datetime.fromtimestamp(newest, timezone.utc).date().isoformat()
    except Exception:
        pass
    return date.today().isoformat()


def recent_commits(limit: int = 30) -> List[dict]:
    """最近 N 条提交（已过滤数据刷新噪音）；本地历史太旧时返回空。"""
    now = time.time()
    if _cache["data"] is not None and now - _cache["at"] < 300:
        return _cache["data"][: max(1, limit)]
    rows: List[dict] = []
    try:
        out = _git("log", f"-{max(1, min(limit, 200))}", "--date=short", "--pretty=format:%ad|%s")
        if out.returncode == 0:
            for line in out.stdout.splitlines():
                if "|" not in line:
                    continue
                date_s, subject = line.split("|", 1)
                subject = subject.strip()
                m = __import__("re").search(r"[A-Za-z]", subject)
                if m and m.start() > 0:
                    subject = subject[m.start():]
                if not subject or subject.startswith("chore(dataset): refresh"):
                    continue
                rows.append({"date": date_s.strip(), "subject": subject})
    except Exception:
        rows = []

    if rows:
        try:
            newest = datetime.strptime(rows[0]["date"], "%Y-%m-%d").date()
            if (date.today() - newest).days > STALE_DAYS:
                rows = []  # 本地副本太旧，宁可回退到静态记录
        except Exception:
            pass

    _cache.update(at=now, data=rows)
    return rows[: max(1, limit)]
