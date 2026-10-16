"""字符 n-gram 词向量相似度（纯标准库，无外部依赖）。

向量 = 字符 bigram+trigram 的词频计数（top-K 特征），余弦相似度判断相似。
校准数据：灌水改写对 0.55-0.86，无关文本 0.00——阈值 0.4 余量充足。
作为 MinHash 预筛之后的精确认证层使用；未来可替换为神经网络
embedding（如 fastembed），保持 build_embedding / cosine / encode / decode 接口不变。
"""
import json
import math
from collections import Counter
from typing import Dict, Optional

DEFAULT_MAX_FEATURES = 256


def _grams(text: str):
    for n in (2, 3):
        for i in range(len(text) - n + 1):
            yield text[i : i + n]


def build_embedding(text: str, max_features: int = DEFAULT_MAX_FEATURES) -> Dict[str, float]:
    """{gram: 词频计数} 稀疏向量，只保留频次最高的 max_features 个特征。"""
    tf = Counter(_grams(text))
    if not tf:
        return {}
    if len(tf) > max_features:
        tf = Counter(dict(tf.most_common(max_features)))
    return dict(tf)


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    dot = sum(v * large.get(k, 0.0) for k, v in small.items())
    if dot == 0.0:
        return 0.0
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def encode(emb: Dict[str, float]) -> Optional[str]:
    return json.dumps(emb, ensure_ascii=False) if emb else None


def decode(value: Optional[str]) -> Dict[str, float]:
    if not value:
        return {}
    try:
        out = json.loads(value)
        return out if isinstance(out, dict) else {}
    except (ValueError, TypeError):
        return {}
