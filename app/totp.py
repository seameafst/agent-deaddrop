"""TOTP（RFC 6238，HMAC-SHA1，30 秒窗口）——纯标准库实现。

管理端点双因子：配置 ADMIN_TOTP_SECRET 后，请求需带 X-Admin-TOTP 头（6 位动态码）。
用 tools/totp.py 生成密钥并导入任意验证器 App（Google Authenticator 等）。
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time

WINDOW_SECONDS = 30


def generate_secret() -> str:
    """生成 base32 密钥（无填充）。"""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    secret = secret.strip().upper().replace(" ", "")
    pad = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret + pad)


def code(secret: str, ts: float = None) -> str:
    counter = int((ts if ts is not None else time.time()) // WINDOW_SECONDS)
    digest = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[off : off + 4])[0] & 0x7FFFFFFF
    return f"{value % 1000000:06d}"


def verify(secret: str, provided: str, window: int = 1) -> bool:
    """允许 ±window 个时间窗口（容忍时钟漂移）。"""
    if not provided or not provided.strip().isdigit():
        return False
    now = time.time()
    for step in range(-window, window + 1):
        if provided.strip() == code(secret, now + step * WINDOW_SECONDS):
            return True
    return False


def otpauth_uri(secret: str, label: str = "deaddrop-admin", issuer: str = "AgentDeadDrop") -> str:
    return (
        f"otpauth://totp/{issuer}:{label}?secret={secret}"
        f"&issuer={issuer}&algorithm=SHA1&digits=6&period={WINDOW_SECONDS}"
    )
