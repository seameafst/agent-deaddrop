"""外链提取：识别留言中的 http(s):// 链接（防钓鱼灌水观测）。"""

import re

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
MAX_LINKS = 20


def extract_links(content: str):
    return URL_RE.findall(content)[:MAX_LINKS]
