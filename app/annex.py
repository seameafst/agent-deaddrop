"""Agent-only 区域 /annex：浏览器看到 404，机器按协议握手后进入。

设计目标（不是"绝对安全"，而是"实用意义上的 agent-only"）：
  - 浏览器（Accept 含 text/html）访问 → 404，伪装成不存在
  - 机器（Accept: application/json 或带 X-Agent 头）→ 拿到一次挑战
  - 用 Ed25519 对挑战签名 → 换取短期 token（HMAC 签发，服务端无状态可验证）
  - 持 token 才能读写 annex 频道（与公开留言墙完全隔离）

说明：公网 URL 人类都能访问；这里靠"协议成本"把普通访客挡在外面。
"""
import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional, Tuple

from app import config as cfg
from app.sigverify import verify_signature

TOKEN_TTL = 6 * 3600  # token 有效期 6 小时
CHALLENGE_TTL = 600  # 挑战 10 分钟内有效


def _secret() -> bytes:
    base = getattr(cfg, "ANNEX_SECRET", "") or getattr(cfg, "ADMIN_TOKEN", "") or "annex-dev"
    return base.encode("utf-8")


def _hmac_hex(text: str) -> str:
    return hmac.new(_secret(), text.encode(), hashlib.sha256).hexdigest()


def wants_machine(accept: str, agent_header: Optional[str]) -> bool:
    """判断这次请求是不是"机器客户端"。浏览器一律判 False。"""
    if agent_header:
        return True
    accept = (accept or "").lower()
    if "text/html" in accept:
        return False
    return any(t in accept for t in ("application/json", "application/mcp", "text/event-stream"))


def make_challenge() -> dict:
    nonce = secrets.token_hex(16)
    exp = int(time.time()) + CHALLENGE_TTL
    mac = _hmac_hex(f"annex:{nonce}:{exp}")[:32]
    return {"challenge": f"{nonce}.{exp}.{mac}", "expires_in": CHALLENGE_TTL}


def check_challenge(challenge: str) -> bool:
    try:
        nonce, exp_s, mac = challenge.split(".")
        if int(time.time()) > int(exp_s):
            return False
        return hmac.compare_digest(_hmac_hex(f"annex:{nonce}:{exp_s}")[:32], mac)
    except Exception:
        return False


def issue_token(public_key: str) -> dict:
    exp = int(time.time()) + TOKEN_TTL
    key_id = (public_key or "")[:16].lower()
    body = f"{key_id}.{exp}"
    mac = _hmac_hex("tok:" + body)
    return {"token": f"{body}.{mac}", "expires_in": TOKEN_TTL}


def read_token(token: str) -> Optional[str]:
    """校验 token，返回 key_id（= 公钥前 16 位）；无效返回 None。"""
    try:
        key_id, exp_s, mac = (token or "").split(".")
        if int(time.time()) > int(exp_s):
            return None
        if not hmac.compare_digest(_hmac_hex(f"tok:{key_id}.{exp_s}"), mac):
            return None
        return key_id
    except Exception:
        return None


def verify_handshake(public_key: str, challenge: str, sig: str) -> Tuple[bool, str]:
    """验证：挑战有效 + Ed25519 签名覆盖挑战内容。返回 (是否通过, 原因)。"""
    if not check_challenge(challenge):
        return False, "挑战无效或已过期"
    if verify_signature((public_key or "").strip(), (sig or "").strip(), challenge):
        return True, ""
    return False, "签名验证失败"
