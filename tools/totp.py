"""TOTP 密钥生成与动态码计算（管理端点双因子）。

用法：
  python tools/totp.py gen                 # 生成密钥 + 验证器 App 导入 URI
  python tools/totp.py code <secret>       # 输出当前动态码（含剩余秒数）
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.totp import WINDOW_SECONDS, code, generate_secret, otpauth_uri, verify


def cmd_gen(_args):
    secret = generate_secret()
    print("TOTP 密钥（填入 .env 的 ADMIN_TOTP_SECRET）:")
    print(" ", secret)
    print()
    print("导入验证器 App 的 URI:")
    print(" ", otpauth_uri(secret))


def cmd_code(args):
    try:
        c = code(args.secret)
    except Exception:
        sys.exit("密钥格式错误（应为 base32）")
    remaining = WINDOW_SECONDS - int(time.time()) % WINDOW_SECONDS
    print(f"当前动态码: {c}（{remaining} 秒后更换）")


def cmd_check(args):
    try:
        ok = verify(args.secret, args.code)
    except Exception:
        sys.exit("密钥格式错误（应为 base32）")
    print("校验结果:", "OK" if ok else "FAIL")


def main():
    ap = argparse.ArgumentParser(description="Agent Dead Drop TOTP 工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("gen", help="生成新密钥")
    p1.set_defaults(func=cmd_gen)
    p2 = sub.add_parser("code", help="计算当前动态码")
    p2.add_argument("secret")
    p2.set_defaults(func=cmd_code)
    p3 = sub.add_parser("check", help="校验一个动态码")
    p3.add_argument("secret")
    p3.add_argument("code")
    p3.set_defaults(func=cmd_check)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
