"""相似度去重：字符 bigram 的 MinHash 草图（Jaccard 估计）。

每条留言存 64 个 min-hash 值（TEXT，128 hex 字符），
新内容与最近存量的估计 Jaccard 相似度 >= 阈值即视为疑似灌水。
比 SimHash 阈值更适合短中文文本（换词改写也能抓）。
纯标准库，跨进程/跨重启稳定（FNV-1a + 显式排序，不依赖内置 hash）。
"""
from typing import List

K = 128
MAX_GRAMS = 1024  # 超长文本只取排序后的前 N 个 bigram，控制计算量
_FNV_OFFSET = 0x811C9DC5
_FNV_PRIME = 0x01000193
_MAX32 = 0xFFFFFFFF


def _hash32(gram: bytes, seed: int) -> int:
    h = _FNV_OFFSET
    for byte in seed.to_bytes(4, "little") + gram:
        h ^= byte
        h = (h * _FNV_PRIME) & 0xFFFFFFFF
    return h


def _grams(text: str) -> List[str]:
    grams = {text[i : i + 2] for i in range(len(text) - 1)}
    if len(grams) < 2:
        grams = {text}
    return sorted(grams)[:MAX_GRAMS]


def sketch(text: str) -> List[int]:
    """字符 bigram 的 64 值 MinHash 草图。"""
    s = [_MAX32] * K
    for gram in _grams(text):
        gb = gram.encode("utf-8")
        for i in range(K):
            h = _hash32(gb, i)
            if h < s[i]:
                s[i] = h
    return s


def sketch_to_hex(s: List[int]) -> str:
    return "".join(f"{v:08x}" for v in s)


def sketch_from_hex(value: str) -> List[int]:
    return [int(value[i : i + 8], 16) for i in range(0, len(value), 8)]


def jaccard(a: List[int], b: List[int]) -> float:
    """两个 MinHash 草图的估计 Jaccard 相似度（0..1）。"""
    k = min(len(a), len(b))
    if k == 0:
        return 0.0
    return sum(1 for i in range(k) if a[i] == b[i]) / k
