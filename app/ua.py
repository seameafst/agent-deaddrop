"""User-Agent 归类：把访客 UA 归到厂商 / AI 爬虫家族，用于观测"谁来了"。

顺序敏感：先匹配具体爬虫，再匹配通用 bot，最后脚本与浏览器。
"""
import re
from typing import Tuple

_RULES: Tuple[Tuple[str, str], ...] = (
    ("OpenAI", r"gptbot|oai-searchbot|chatgpt-user|openai"),
    ("Anthropic", r"claudebot|claude-web|claude-user|anthropic"),
    ("Perplexity", r"perplexitybot|perplexity-user"),
    ("Google", r"googlebot|google-extended|googleother|google-inspectiontool"),
    ("Bing", r"bingbot|bingpreview|adidxbot"),
    ("ByteDance", r"bytespider|tiktokspider"),
    ("Apple", r"applebot"),
    ("Amazon", r"amazonbot"),
    ("Meta", r"facebookbot|meta-externalagent|facebookexternalhit"),
    ("CommonCrawl", r"ccbot"),
    ("Yandex", r"yandexbot"),
    ("Baidu", r"baiduspider"),
    ("DuckDuckGo", r"duckduckbot"),
    ("Cohere", r"cohere-ai"),
    ("You.com", r"youbot"),
    ("Diffbot", r"diffbot"),
    ("AI2", r"ai2bot"),
    # —— SEO / 测量类爬虫（2026-10-22 实测抓到，放在"其他爬虫"之前才能优先命中）
    ("SERPstat", r"serpstatbot"),
    ("Fossick", r"fossickbot"),
    ("InternetMeasurement", r"internetmeasurement"),
    ("伪造爬虫", r"cms-checker|example\.com"),
    ("其他爬虫", r"bot|crawler|spider|scrape|feedfetcher|monitor"),
    (
        "自动化脚本",
        r"python-requests|python-urllib|urllib|httpx|curl|wget|go-http-client"
        r"|java/|node-fetch|axios|okhttp|powershell|libwww|httpclient",
    ),
    ("浏览器", r"mozilla|chrome|safari|firefox|edg/"),
)

# 这些家族代表"AI 相关流量"（AI 爬虫 / 搜索引擎的 AI 索引）
AI_FAMILIES = frozenset(
    {
        "OpenAI",
        "Anthropic",
        "Perplexity",
        "Google",
        "Bing",
        "ByteDance",
        "Apple",
        "Amazon",
        "Meta",
        "CommonCrawl",
        "Yandex",
        "Baidu",
        "DuckDuckGo",
        "Cohere",
        "You.com",
        "Diffbot",
        "AI2",
    }
)


def classify(user_agent: str) -> str:
    ua = (user_agent or "").strip()
    if not ua:
        return "空 UA"
    low = ua.lower()
    for family, pattern in _RULES:
        if re.search(pattern, low):
            return family
    return "其他"


def is_ai(family: str) -> bool:
    return family in AI_FAMILIES
