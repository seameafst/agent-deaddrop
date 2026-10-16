"""域名信誉：本地黑名单匹配（纯函数，数据在存储层的 blocklist 表）。

匹配规则：精确域名或子域名命中即视为黑名单
（如黑名单含 evil.example，则 evil.example 与 x.evil.example 都命中）。
"""
from typing import List
from urllib.parse import urlparse


def host_of(url: str) -> str:
    try:
        host = urlparse(url.strip()).hostname
    except ValueError:
        return ""
    return (host or "").lower().strip(".")


def is_blocked_host(host: str, blocked: List[str]) -> bool:
    host = (host or "").lower().strip(".")
    if not host:
        return False
    for b in blocked:
        b = (b or "").lower().strip(".")
        if not b:
            continue
        if host == b or host.endswith("." + b):
            return True
    return False
