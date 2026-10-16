"""Ed25519 签名验证（防冒名 + 防重放）。

签名载荷（UTF-8，逐行拼接）：
    归一化content + "\\n" + 一次性nonce + "\\n" + 请求 Host（小写，含端口）

nonce 由服务端 POST /challenge 签发：单次使用、默认 300 秒过期。
服务端先消费 nonce 再验签——旧签名、跨站签名、重放签名全部失效。
验签独立可复现：nonce 随消息公开落库，任何人拿公钥 + 原文 + nonce + Host 都能重新验证。
"""
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def normalize_content(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip()).lower()


def build_sign_payload(content: str, nonce: str, domain: str) -> str:
    return f"{normalize_content(content)}\n{nonce.strip()}\n{domain.strip().lower()}"


def verify_signature(public_key_hex: str, sig_hex: str, payload: str) -> bool:
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
    except (ValueError, TypeError):
        return False
    try:
        pub.verify(bytes.fromhex(sig_hex), payload.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
