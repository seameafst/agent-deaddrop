"""实时域名信誉查询（可选增强层，需联网）。

- URLhaus host API（免密钥）：https://urlhaus-api.abuse.ch/v1/host/
- VirusTotal domains API（需 VIRUSTOTAL_API_KEY）
带内存缓存（默认 24h）与超时降级：查询失败视为未知（放行），
本地黑名单（app/domainrep.py）仍是主防线，本模块是实时补充。
"""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional

import app.config as cfg

URLHAUS_HOST_API = "https://urlhaus-api.abuse.ch/v1/host/"
VT_DOMAINS_API = "https://www.virustotal.com/api/v3/domains/"

_cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 24 * 3600


def _cached(host: str) -> Optional[dict]:
    with _cache_lock:
        hit = _cache.get(host)
        if hit and time.time() - hit[1] < _CACHE_TTL:
            return hit[0]
        return None


def _store(host: str, verdict: dict) -> None:
    with _cache_lock:
        _cache[host] = (verdict, time.time())
        if len(_cache) > 4096:
            _cache.clear()


def _urlhaus(host: str, timeout: int) -> Optional[dict]:
    data = urllib.parse.urlencode({"host": host}).encode()
    req = urllib.request.Request(
        URLHAUS_HOST_API,
        data=data,
        headers={"User-Agent": "deaddrop-repcheck/0.1", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode("utf-8", errors="replace"))
    if body.get("query_status") == "no_results":
        return {"listed": False, "source": "urlhaus"}
    blacklists = body.get("blacklists") or {}
    refs = body.get("urlhaus_references") or []
    listed = any(v == "listed" for v in blacklists.values()) or bool(refs)
    return {"listed": listed, "source": "urlhaus", "blacklists": blacklists, "refs": len(refs)}


def _virustotal(host: str, timeout: int) -> Optional[dict]:
    if not cfg.VIRUSTOTAL_API_KEY:
        return None
    req = urllib.request.Request(
        VT_DOMAINS_API + host,
        headers={"x-apikey": cfg.VIRUSTOTAL_API_KEY, "User-Agent": "deaddrop-repcheck/0.1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode("utf-8", errors="replace"))
    stats = (body.get("data") or {}).get("attributes", {}).get("last_analysis_stats") or {}
    return {
        "listed": stats.get("malicious", 0) > 0,
        "source": "virustotal",
        "malicious": stats.get("malicious", 0),
        "total": sum(stats.values()),
    }


def check_host(host: str) -> Optional[dict]:
    """返回 {"listed": bool, "source": ..., ...}；查询失败返回 None（未知，放行）。"""
    host = (host or "").lower().strip(".")
    if not host:
        return None
    hit = _cached(host)
    if hit is not None:
        return hit
    timeout = max(cfg.REP_API_TIMEOUT, 2)
    verdict = None
    try:
        verdict = _urlhaus(host, timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        verdict = None
    if verdict is None:
        try:
            verdict = _virustotal(host, timeout)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            verdict = None
    if verdict is None:
        return None  # 不缓存失败，下次重试
    _store(host, verdict)
    return verdict
