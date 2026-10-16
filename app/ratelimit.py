"""内存级滑动窗口限流（按来源 IP）。

单实例够用；serverless 多实例部署下只是近似值（每个实例各算各的）。
"""
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_hits: int, window_seconds: int):
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits = defaultdict(deque)

    def _prune(self, key: str, now: float) -> None:
        dq = self._hits[key]
        while dq and now - dq[0] >= self.window:
            dq.popleft()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        self._prune(key, now)
        if len(self._hits[key]) >= self.max_hits:
            return False
        self._hits[key].append(now)
        return True

    def retry_after(self, key: str) -> int:
        dq = self._hits.get(key)
        if not dq:
            return 0
        return max(0, int(self.window - (time.monotonic() - dq[0])))
