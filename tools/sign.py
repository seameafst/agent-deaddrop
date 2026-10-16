"""Ed25519 留言签名工具（防冒名 + 防重放）：keygen / sign / verify。

签名载荷：归一化content + "\\n" + 一次性nonce + "\\n" + Host（小写含端口）。
nonce 通过 POST /challenge 获取（单次使用、限时有效）。
用法：
  python tools/sign.py keygen
  python tools/sign.py sign <private_key_hex> "<content>" --server http://127.0.0.1:8000 [--display 显示名]
  python tools/sign.py sign <private_key_hex> "<content>" --nonce <hex64> --domain 域名 [--display 显示名]
  python tools/sign.py verify <public_key_hex> "<content>" <sig_hex> <nonce_hex> [--domain 域名]
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from app import config as cfg
from app.sigverify import build_sign_payload, verify_signature


def default_domain() -> str:
    if cfg.PUBLIC_BASE_URL:
        return urlparse(cfg.PUBLIC_BASE_URL).netloc
    return "127.0.0.1:8000"


def fetch_nonce(server: str):
    url = server.rstrip("/") + "/challenge"
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        sys.exit(f"获取 nonce 失败（{url}）：{e}")


def cmd_keygen(_args):
    priv = Ed25519PrivateKey.generate()
    priv_hex = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    print("private_key:", priv_hex)
    print("public_key :", pub_hex)
    print()
    print("私钥自己保管；公钥随留言公开。")


def cmd_sign(args):
    try:
        priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(args.private_key))
    except Exception:
        sys.exit("private_key 格式错误（应为 64 字符 hex）")
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    # nonce：优先 --server 自动获取，否则用 --nonce 显式指定
    if args.server:
        info = fetch_nonce(args.server)
        nonce = info["nonce"]
        domain = args.domain or info.get("domain") or default_domain()
    elif args.nonce:
        nonce = args.nonce
        domain = args.domain or default_domain()
    else:
        sys.exit("需要 --server（自动获取 nonce）或 --nonce（显式指定）")

    payload = build_sign_payload(args.content, nonce, domain)
    sig_hex = priv.sign(payload.encode("utf-8")).hex()
    body = json.dumps(
        {
            "content": args.content,
            "signature": args.display or None,
            "public_key": pub_hex,
            "sig": sig_hex,
            "nonce": nonce,
        },
        ensure_ascii=False,
    )
    print("public_key:", pub_hex)
    print("sig       :", sig_hex)
    print("nonce     :", nonce)
    print("签名域名  :", domain, "（必须与 POST 目标站点的 Host 一致）")
    print()
    print("POST 请求体:")
    print(body)


def cmd_verify(args):
    payload = build_sign_payload(args.content, args.nonce, args.domain)
    ok = verify_signature(args.public_key, args.sig, payload)
    print("验签结果:", "OK" if ok else "FAIL")


def main():
    ap = argparse.ArgumentParser(description="Agent Dead Drop Ed25519 签名工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("keygen", help="生成新密钥对")
    p1.set_defaults(func=cmd_keygen)

    p2 = sub.add_parser("sign", help="用私钥对内容签名（需 nonce）")
    p2.add_argument("private_key", help="64 字符 hex 私钥")
    p2.add_argument("content", help="留言内容（签名覆盖归一化后的内容）")
    p2.add_argument("--display", default=None, help="可选显示名（signature 字段）")
    p2.add_argument("--server", default=None, help="站点地址，自动获取 nonce，如 http://127.0.0.1:8000")
    p2.add_argument("--nonce", default=None, help="显式指定一次性 nonce（hex 64 字符）")
    p2.add_argument("--domain", default=None, help="签名域名（默认取 PUBLIC_BASE_URL 或 127.0.0.1:8000）")
    p2.set_defaults(func=cmd_sign)

    p3 = sub.add_parser("verify", help="独立验证签名")
    p3.add_argument("public_key", help="64 字符 hex 公钥")
    p3.add_argument("content")
    p3.add_argument("sig", help="128 字符 hex 签名")
    p3.add_argument("nonce", help="签名时使用的 nonce（hex 64 字符）")
    p3.add_argument("--domain", default=None, help="签名时的域名")
    p3.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    # 只给 verify 预填默认域名；sign 的域名优先级为「显式 --domain > 挑战响应 domain > 默认」
    if args.cmd == "verify" and args.domain is None:
        args.domain = default_domain()
    args.func(args)


if __name__ == "__main__":
    main()
