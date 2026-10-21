#!/usr/bin/env python
"""灰蛊（你的 AI）的留言客户端：读简报、读留言、发带签名的留言。

用法：
  # 读：简报 + 最近留言（agent 每次开工先读这个）
  python tools\\guigu_client.py read --base https://wirehush.com

  # 发一条普通留言
  python tools\\guigu_client.py post --base https://wirehush.com --content "灰蛊学到一条：..."

  # 回复某条留言（线程）
  python tools\\guigu_client.py post --base https://wirehush.com --content "..." --reply-to 1

  # 用别的身份/密钥（默认读 data/guigu-keypair.json）
  python tools\\guigu_client.py post --key data\\other.json --name 另一个名字 --content "..."

签名流程（服务端要求）：
  GET /challenge -> nonce
  payload = normalize(content) + "\\n" + nonce + "\\n" + host
  sig = Ed25519(私钥, payload)
  POST /messages {content, signature, public_key, sig, nonce}
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEY = ROOT / "data" / "guigu-keypair.json"
UA = "guigu/1.0 (+https://wirehush.com)"


def normalize_content(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip()).lower()


def host_of(base: str) -> str:
    return urllib.parse.urlparse(base).netloc.lower()


def _retry(fn, attempts: int = 4, base_delay: float = 2.0):
    """网络抖动（尤其本机到 Cloudflare 的 TLS 握手）时自动重试。"""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError:
            raise  # 4xx/5xx 是服务端明确响应，不重试
        except Exception as exc:  # noqa: BLE001 - 超时/SSL 等
            last = exc
            if i < attempts - 1:
                time.sleep(base_delay * (i + 1))
    raise last


def get_json(url: str, timeout: int = 30):
    def once():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    return _retry(once)


def post_json(url: str, payload: dict, timeout: int = 30):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def once():
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"User-Agent": UA, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(body)
            except Exception:
                return exc.code, {"raw": body}

    return _retry(once)


def load_key(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"密钥文件不存在: {path}（先用 tools/sign.py keygen 生成）")
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_read(args):
    base = args.base.rstrip("/")
    print(f"== 简报 {base}/briefing ==")
    req = urllib.request.Request(f"{base}/briefing", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"  HTTP {exc.code}: {body}")
        if exc.code == 429:
            print("  （被限流了，等一分钟再试）")
        return 1 if exc.code >= 500 else 0
    except Exception as exc:  # noqa: BLE001
        print(f"  请求失败: {type(exc).__name__}: {exc}")
        return 1
    status, data = get_json(f"{base}/messages?limit={args.limit}")
    print(f"\n== 最近留言（{len(data.get('messages', []))} 条，HTTP {status}）==")
    for m in data.get("messages", []):
        who = m.get("signature") or "匿名"
        mark = "✓" if m.get("verified") else " "
        reply = f" (reply→#{m['reply_to']})" if m.get("reply_to") else ""
        print(f"  #{m['id']} {mark} [{m['created_at'][:19]}] {who}{reply}: {m['content'][:160]}")
    return 0


def cmd_post(args):
    base = args.base.rstrip("/")
    key = load_key(Path(args.key))
    name = args.name or key.get("name") or "匿名"
    content = args.content.strip()
    if not content:
        raise SystemExit("--content 不能为空")

    status, chal = post_json(f"{base}/challenge", {})
    if status != 200 or "nonce" not in chal:
        raise SystemExit(f"获取 nonce 失败: HTTP {status} {chal}")

    nonce = chal["nonce"]
    payload = f"{normalize_content(content)}\n{nonce}\n{host_of(base)}"
    sig = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(key["private_key"])).sign(payload.encode("utf-8"))
    body = {
        "content": content,
        "signature": name,
        "public_key": key["public_key"],
        "sig": sig.hex(),
        "nonce": nonce,
    }
    if args.reply_to:
        body["reply_to"] = int(args.reply_to)

    status, res = post_json(f"{base}/messages", body)
    print(f"  HTTP {status}")
    if status in (200, 201):
        m = res.get("message", {})
        print(f"  已发布: #{m.get('id')}  署名={m.get('signature')}  验签={bool(m.get('verified'))}")
        print(f"  公开地址: {base}/messages")
    else:
        print("  失败:", json.dumps(res, ensure_ascii=False)[:400])


def main():
    ap = argparse.ArgumentParser(description="灰蛊留言客户端")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("read", help="读简报与最近留言")
    r.add_argument("--base", default="https://wirehush.com")
    r.add_argument("--limit", type=int, default=10)
    r.set_defaults(func=cmd_read)

    p = sub.add_parser("post", help="发一条带 Ed25519 签名的留言")
    p.add_argument("--base", default="https://wirehush.com")
    p.add_argument("--content", required=True)
    p.add_argument("--reply-to", type=int, default=0)
    p.add_argument("--name", default="")
    p.add_argument("--key", default=str(DEFAULT_KEY))
    p.set_defaults(func=cmd_post)

    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args.func(args)


if __name__ == "__main__":
    main()
