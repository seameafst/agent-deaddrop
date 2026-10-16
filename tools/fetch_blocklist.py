"""拉取公开威胁情报，把恶意域名灌进本地信誉黑名单。

默认源：URLhaus（abuse.ch）文本 feed，一行一个恶意 URL，取域名入库。
用法（在 agent-deaddrop 目录下，先按需设置 STORAGE_BACKEND/SUPABASE_* 环境变量）：
  python tools/fetch_blocklist.py            # 默认取前 500 个域名
  python tools/fetch_blocklist.py --limit 2000
"""
import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domainrep import host_of
from app.storage import get_storage

URLHAUS_TEXT = "https://urlhaus.abuse.ch/downloads/text/"


def fetch_urlhaus(limit: int):
    req = urllib.request.Request(
        URLHAUS_TEXT, headers={"User-Agent": "deaddrop-blocklist-fetcher/0.1"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        lines = r.read().decode("utf-8", errors="replace").splitlines()
    domains = []
    for line in lines:
        host = host_of(line)
        if host and host not in domains:
            domains.append(host)
        if len(domains) >= limit:
            break
    return domains


def main():
    ap = argparse.ArgumentParser(description="拉取公开威胁情报进本地域名黑名单")
    ap.add_argument("--limit", type=int, default=500, help="最多入库多少个域名")
    args = ap.parse_args()

    print(f"从 URLhaus 拉取（上限 {args.limit}）…")
    try:
        domains = fetch_urlhaus(args.limit)
    except Exception as e:
        sys.exit(f"拉取失败：{e}")
    if not domains:
        sys.exit("没有拿到域名，检查网络后重试。")

    storage = get_storage()
    reason = "urlhaus"
    added = 0
    for d in domains:
        try:
            storage.blocklist_add(d, reason)
            added += 1
        except Exception as e:
            print(f"  跳过 {d}：{e}")
    print(f"完成：{added} 个域名进入黑名单（reason={reason}）。")
    print("提示：黑名单对已入库的旧留言不回扫，只拦截新留言。")


if __name__ == "__main__":
    main()
