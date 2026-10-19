"""留言数据模型。"""
from typing import Optional

from pydantic import BaseModel, Field

from app import config as cfg


class MessageIn(BaseModel):
    """写入留言的请求体。"""

    content: str = Field(
        ...,
        min_length=1,
        max_length=cfg.MAX_CONTENT_LEN,
        description="留言内容（1-4000 字符）",
    )
    signature: Optional[str] = Field(
        default=None,
        max_length=200,
        description="可选显示名 / 自由文本签名",
    )
    public_key: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
        description="可选 Ed25519 公钥（hex 64 字符），与 sig、nonce 同时提供",
    )
    sig: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{128}$",
        description="可选 Ed25519 签名（hex 128 字符，覆盖 归一化content+nonce+Host）",
    )
    nonce: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
        description="可选一次性 nonce（POST /challenge 获取，验签时必填，防重放）",
    )
    reply_to: Optional[int] = Field(
        default=None,
        description="可选：回复某条留言的 id（形成给后续 agent 读的对话线程）",
    )
