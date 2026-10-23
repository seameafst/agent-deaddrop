"""数据集新鲜度检查：远端 GitHub 上的脱敏数据集是否按时刷新。

管理台用它判断「GitHub Actions 是否还在正常跑」：
  - 远端 dataset/public-export.json 的 exported_at 距今多久
  - 超过 FRESH_HOURS 视为过期（Actions 可能失败或站点长期离线）
  - 顺带查最近一次 Actions run 的结论

带 5 分钟成功缓存 / 1 分钟失败缓存，避免每次刷新管理台都打一次 GitHub。
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DATASET_URL = "https://raw.githubusercontent.com/seameafst/agent-deaddrop/main/dataset/public-export.json"
ACTIONS_URL = "https://api.github.com/repos/seameafst/agent-deaddrop/actions/runs?per_page=1"
FRESH_HOURS = 36  # 每天刷新一次；超过 36 小时基本可判定异常
UA = "deaddrop-admin/1.0"

_cache = {"at": 0.0, "data": None, "error": None}


def _get_json(url: str, retries: int = 3, timeout: int = 15):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - 网络类异常统一重试
            last = exc
            if i < retries - 1:
                time.sleep(1 + i)
    # 回退：某些环境里 Python 的 TLS 握手不稳定，用系统 curl 再试一次
    # （写到临时文件而不是管道，规避受限环境对管道的限制）
    try:
        import shutil
        import subprocess
        import tempfile

        curl = shutil.which("curl") or shutil.which("curl.exe")
        if curl:
            fd, tmp = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            try:
                subprocess.run(
                    [curl, "-sL", "--max-time", str(timeout), "-o", tmp, url],
                    check=False,
                    timeout=timeout + 10,
                )
                with open(tmp, "rb") as fh:
                    raw = fh.read()
                if raw:
                    return json.loads(raw.decode("utf-8", errors="replace"))
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    except Exception:
        pass
    raise last


def _parse_age_hours(exported: str) -> Optional[float]:
    if not exported:
        return None
    try:
        t = datetime.fromisoformat(exported.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 3600.0
    except Exception:
        return None


def status(force: bool = False) -> dict:
    now = time.time()
    if not force and _cache["data"] is not None and now - _cache["at"] < 300:
        return _cache["data"]
    if not force and _cache["error"] is not None and now - _cache["at"] < 60:
        return _cache["error"]

    try:
        ds = _get_json(DATASET_URL)
        exported = ds.get("exported_at") or ""
        age = _parse_age_hours(exported)
        fresh = age is not None and age <= FRESH_HOURS

        actions = None
        try:
            runs = _get_json(ACTIONS_URL, retries=2)
            items = runs.get("workflow_runs") or []
            if items:
                r0 = items[0]
                actions = {
                    "status": r0.get("status"),
                    "conclusion": r0.get("conclusion"),
                    "started_at": r0.get("run_started_at"),
                    "url": r0.get("html_url"),
                }
        except Exception:
            actions = None

        out = {
            "ok": True,
            "exported_at": exported,
            "age_hours": round(age, 1) if age is not None else None,
            "fresh": fresh,
            "threshold_hours": FRESH_HOURS,
            "site": ds.get("site"),
            "counts": ds.get("counts"),
            "actions": actions,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _cache.update(at=now, data=out, error=None)
        return out
    except Exception as exc:  # noqa: BLE001
        out = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _cache.update(at=now, data=None, error=out)
        return out


_hist_cache = {"at": 0.0, "data": None}
_refreshing = {"flag": False}
LOCAL_DATASET = Path(__file__).resolve().parent.parent / "dataset" / "public-export.json"


def _local_history():
    """本地仓库里的数据集副本（有 history 就直接用，毫秒级）。"""
    try:
        if not LOCAL_DATASET.exists():
            return None
        ds = json.loads(LOCAL_DATASET.read_text(encoding="utf-8"))
        items = [h for h in (ds.get("history") or []) if isinstance(h, dict)]
        return items or None
    except Exception:
        return None


def _refresh_remote_history():
    """后台线程：从 GitHub 拉最新数据集，更新 history 缓存（不阻塞请求）。"""
    try:
        ds = _get_json(DATASET_URL)
        items = [h for h in (ds.get("history") or []) if isinstance(h, dict)]
        if items:
            _hist_cache.update(at=time.time(), data=items)
    except Exception:
        pass
    finally:
        _refreshing["flag"] = False


def history(days: int = 30) -> dict:
    """每日快照（趋势图用）。

    策略：远端缓存（1 小时）> 本地仓库副本（毫秒级）> 后台线程刷新远端。
    远端抓取很慢，所以永远不阻塞请求——先给能给的，下一次刷新再补最新。
    """
    days = max(1, min(int(days), 365))
    now = time.time()
    if _hist_cache["data"] is not None and now - _hist_cache["at"] < 3600:
        return {"ok": True, "days": days, "entries": _hist_cache["data"][-days:], "source": "cache"}
    if not _refreshing["flag"]:
        _refreshing["flag"] = True
        threading.Thread(target=_refresh_remote_history, daemon=True).start()
    local = _local_history()
    if local is not None:
        return {"ok": True, "days": days, "entries": local[-days:], "source": "local"}
    cached = _hist_cache["data"]
    if cached:
        return {"ok": True, "days": days, "entries": cached[-days:], "source": "stale-cache"}
    return {"ok": True, "days": days, "entries": [], "source": "pending",
            "note": "首次从远端拉取中，稍后刷新即可"}
