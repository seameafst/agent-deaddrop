#!/usr/bin/env python
"""用 Cloudflare API 一次性完成建站准备：

  1. 找到（或创建）wirehush.com 这个 zone，输出 Cloudflare 分配的两条 NS
  2. 创建命名隧道（若已存在则复用）
  3. 写隧道 ingress 配置：<域名> -> http://localhost:8000
  4. 建 DNS 记录：<域名> CNAME <tunnel-id>.cfargotunnel.com（橙云代理）
  5. 取连接令牌（connector token），打印出来供 cutover_cloudflare.ps1 使用

用法：
  python tools/cloudflare_setup.py --token <API_TOKEN> [--domain wirehush.com]

需要 API 令牌具备：
  Account: Cloudflare Tunnel -> Edit
  Account: Account Settings  -> Read
  Zone: Zone -> Edit
  Zone: DNS  -> Edit
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.cloudflare.com/client/v4"


def configure_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class CF:
    def __init__(self, token: str):
        self.token = token

    def req(self, method: str, path: str, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail[:500]}") from None

        if not payload.get("success", True):
            raise RuntimeError(f"{method} {path} -> API 错误: {json.dumps(payload.get('errors'), ensure_ascii=False)[:500]}")
        return payload.get("result")


def pick_account(cf: CF) -> dict:
    accounts = cf.req("GET", "/accounts") or []
    if not accounts:
        raise RuntimeError("令牌下没有可用账户（Account 权限不足？）")
    if len(accounts) > 1:
        print(f"  账户列表: {[a.get('name') for a in accounts]}")
        print(f"  使用第一个: {accounts[0].get('name')}")
    return accounts[0]


def ensure_zone(cf: CF, domain: str, account_id: str) -> dict:
    found = cf.req("GET", f"/zones?name={domain}") or []
    if found:
        print(f"  zone 已存在: {found[0]['id']}")
        return found[0]
    print("  zone 不存在，创建中…")
    zone = cf.req(
        "POST",
        "/zones",
        {"name": domain, "account": {"id": account_id}, "type": "full"},
    )
    print(f"  已创建 zone: {zone['id']}")
    return zone


def ensure_tunnel(cf: CF, account_id: str, name: str) -> dict:
    tunnels = cf.req("GET", f"/accounts/{account_id}/cfd_tunnel?name={name}&is_deleted=false") or []
    if tunnels:
        print(f"  隧道已存在: {tunnels[0]['id']}")
        return tunnels[0]
    print("  创建隧道…")
    tunnel = cf.req(
        "POST",
        f"/accounts/{account_id}/cfd_tunnel",
        {"name": name, "config_src": "cloudflare"},
    )
    print(f"  已创建隧道: {tunnel['id']}")
    return tunnel


def main():
    configure_stdout()
    ap = argparse.ArgumentParser(description="Cloudflare API 建 zone/隧道/DNS 并取连接令牌")
    ap.add_argument("--token", required=True, help="Cloudflare API 令牌")
    ap.add_argument("--domain", default="wirehush.com")
    ap.add_argument("--tunnel-name", default="wirehush")
    ap.add_argument("--origin", default="http://localhost:8000")
    args = ap.parse_args()

    cf = CF(args.token)
    print("== 1. 账户 ==")
    account = pick_account(cf)
    account_id = account["id"]
    print(f"  账户: {account.get('name')} ({account_id})")

    print("== 2. zone ==")
    zone = ensure_zone(cf, args.domain, account_id)
    zone_id = zone["id"]
    ns = zone.get("name_servers") or []
    print(f"  zone id: {zone_id}")
    if ns:
        print(f"  ✴ 请到阿里云把 NS 改成这两条: {ns[0]} / {ns[1] if len(ns) > 1 else ''}")
    else:
        print("  （zone 未返回 name_servers，稍后可在控制台查看）")

    print("== 3. 隧道 ==")
    tunnel = ensure_tunnel(cf, account_id, args.tunnel_name)
    tunnel_id = tunnel["id"]
    print(f"  tunnel id: {tunnel_id}")

    print("== 4. ingress 配置 ==")
    cf.req(
        "PUT",
        f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
        {"config": {"ingress": [{"hostname": args.domain, "service": args.origin}, {"service": "http_status:404"}]}},
    )
    print(f"  {args.domain} -> {args.origin}")

    print("== 5. DNS 记录 ==")
    existing = cf.req("GET", f"/zones/{zone_id}/dns_records?name={args.domain}") or []
    target = f"{tunnel_id}.cfargotunnel.com"
    if existing:
        rec = existing[0]
        print(f"  已存在: {rec['type']} {rec['name']} -> {rec['content']} (proxied={rec.get('proxied')})")
        if rec["type"] != "CNAME" or rec["content"] != target:
            cf.req(
                "PUT",
                f"/zones/{zone_id}/dns_records/{rec['id']}",
                {"type": "CNAME", "name": args.domain, "content": target, "proxied": True},
            )
            print("  已更新为隧道 CNAME")
    else:
        cf.req(
            "POST",
            f"/zones/{zone_id}/dns_records",
            {"type": "CNAME", "name": args.domain, "content": target, "proxied": True},
        )
        print(f"  已创建: CNAME {args.domain} -> {target} (proxied)")

    print("== 6. 连接令牌 ==")
    token = cf.req("POST", f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token")
    if isinstance(token, dict):
        token = token.get("token") or json.dumps(token)
    token = str(token)
    if not token or len(token) < 50:
        raise RuntimeError(f"未能取得连接令牌: {token[:200]}")
    # 直接落盘：避免令牌出现在命令行、日志或终端回滚里
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "cloudflared-token.txt"), "w", encoding="utf-8") as fh:
        fh.write(token)
    with open(os.path.join(data_dir, "cloudflared-domain.txt"), "w", encoding="utf-8") as fh:
        fh.write(args.domain)
    print(f"  已写入 data/cloudflared-token.txt（长度 {len(token)}，不打印明文）")

    print()
    print("===== 完成 =====")
    print(f"DOMAIN={args.domain}")
    print(f"ZONE_ID={zone_id}")
    print(f"ACCOUNT_ID={account_id}")
    print(f"TUNNEL_ID={tunnel_id}")
    print(f"NAME_SERVERS={(ns[0] + ',' + ns[1]) if len(ns) > 1 else ''}")
    print("CONNECTOR_TOKEN=（已写入 data/cloudflared-token.txt）")


if __name__ == "__main__":
    main()
