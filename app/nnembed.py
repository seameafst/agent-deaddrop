"""神经网络 embedding 精确认证（可选增强层）。

需要：pip install -r requirements-nn.txt（fastembed + onnxruntime），
且首次使用能联网下载模型（默认 BAAI/bge-small-zh-v1.5，约 100MB）。

**非阻塞设计**：初始化在后台线程进行，初始化期间 available() 直接返回 False，
调用方回退字符 n-gram 词向量——绝不阻塞请求（否则模型下不动时服务会假死）。
"""
import math
import threading
from typing import List, Optional

import app.config as cfg

_embedder = None
_init_started = False
_init_done = False
_init_error = ""
_lock = threading.Lock()


def _init() -> None:
    global _embedder, _init_done, _init_error
    emb = None
    err = ""
    try:
        from fastembed import TextEmbedding

        emb = TextEmbedding(model_name=cfg.NN_EMBED_MODEL)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    with _lock:
        _embedder = emb
        _init_error = err
        _init_done = True


def start_init() -> None:
    """启动后台初始化（幂等、不阻塞）。"""
    global _init_started
    with _lock:
        if _init_started:
            return
        _init_started = True
    threading.Thread(target=_init, daemon=True).start()


def available() -> bool:
    """非阻塞：模型可用才返回 True；初始化中/失败/未安装一律 False。"""
    with _lock:
        return _embedder is not None


def init_done() -> bool:
    with _lock:
        return _init_done


def init_error() -> str:
    with _lock:
        return _init_error


def encode(text: str) -> Optional[List[float]]:
    with _lock:
        embedder = _embedder
    if embedder is None:
        return None
    try:
        vec = list(embedder.embed([text]))[0]
        return [float(x) for x in vec]
    except Exception:
        return None


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    if dot == 0.0:
        return 0.0
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
