"""「已验证爬虫」判定：UA 家族 + 来源 ASN 双重匹配。

原理：UA 可以随便伪造，但爬虫通常从自家云出网。把已知爬虫的 UA 家族与它们
实际使用的 ASN 交叉验证，能显著降低"被伪装 UA 骗到"的概率。

    OpenAI (GPTBot)   -> AS8075 / AS8068  (Microsoft Azure)
    Anthropic (ClaudeBot) -> AS16509 / AS14618 (Amazon AWS)
    Google (Googlebot)    -> AS15169 / AS396982
    Bing (Bingbot)        -> AS8075 / AS8068 (Microsoft)
    Apple (Applebot)      -> AS714
    Meta (facebookbot)    -> AS32934
    Baidu (Baiduspider)   -> AS38365
    Yandex (YandexBot)    -> AS13238
    Amazon (Amazonbot)    -> AS16509 / AS14618

未列入的家族（如 Perplexity / ByteDance / CommonCrawl）暂不判定——它们的
出网 ASN 不够确定，宁可显示"未验证"也不误报。
"""
import re
from typing import Tuple

# 家族 -> (允许的 ASN 数字集合, 展示名)
RULES = {
    "OpenAI": ({"8075", "8068"}, "GPTBot"),
    "Anthropic": ({"16509", "14618"}, "ClaudeBot"),
    "Google": ({"15169", "396982"}, "Googlebot"),
    "Bing": ({"8075", "8068"}, "Bingbot"),
    "Apple": ({"714"}, "Applebot"),
    "Amazon": ({"16509", "14618"}, "Amazonbot"),
    "Meta": ({"32934"}, "Meta"),
    "Baidu": ({"38365"}, "Baiduspider"),
    "Yandex": ({"13238"}, "YandexBot"),
    # 2026-10-22 实测观察到的出网 ASN（非官方公布，命中即视为来源一致）
    "SERPstat": ({"24940"}, "SerpstatBot"),
    "Fossick": ({"51167"}, "FossickBot"),
    "InternetMeasurement": ({"211298"}, "InternetMeasurement"),
}

# 这些家族本身就是"伪造"的信号，不论 ASN 都判定为可疑
FAKE_FAMILIES = {"伪造爬虫"}


def _asn_number(asn: str) -> str:
    """从 "AS8075 Microsoft Corporation" 这类字符串里取出纯数字。"""
    m = re.search(r"AS\s*(\d+)", asn or "", re.I)
    return m.group(1) if m else ""


def verify(family: str, asn: str) -> Tuple[bool, str]:
    """返回 (是否已验证, 展示名)。未列入规则或 ASN 不匹配时返回 (False, '')。"""
    rule = RULES.get(family or "")
    if not rule:
        return False, ""
    allowed, label = rule
    num = _asn_number(asn)
    if not num:
        return False, ""
    return (num in allowed), label


def verdict_text(family: str, asn: str) -> str:
    """给管理端展示的一行判定：已验证 / 疑似冒充 / 伪造 / 未验证。"""
    if (family or "") in FAKE_FAMILIES:
        return "🚨 伪造 UA（示例域名 / 检查器伪装）"
    ok, label = verify(family, asn)
    if ok:
        return f"✅ 已验证 {label}"
    if (family or "") in RULES:
        num = _asn_number(asn)
        if num:
            return f"🚨 疑似冒充 {label}（AS{num} 不在官方网段）"
        return "⚠️ 未验证（缺少 ASN 信息）"
    return ""


def spoof_suspect(family: str, asn: str) -> bool:
    """声称是已知爬虫家族，但来源 ASN 不在其官方网段 —— 疑似伪造 UA。

    没有 ASN 信息时返回 False（不下没有证据的结论）。
    """
    if (family or "") in FAKE_FAMILIES:
        return True
    rule = RULES.get(family or "")
    if not rule:
        return False
    num = _asn_number(asn)
    if not num:
        return False
    allowed, _ = rule
    return num not in allowed


def annotate(rows):
    """给一组记录批量补上 bot_verified / bot_label / bot_verdict / spoof_suspect。"""
    out = []
    for r in rows:
        d = dict(r)
        fam = d.get("ua_family") or ""
        asn = d.get("asn") or ""
        ok, label = verify(fam, asn)
        d["bot_verified"] = ok
        d["bot_label"] = label
        d["spoof_suspect"] = spoof_suspect(fam, asn)
        d["bot_verdict"] = verdict_text(fam, asn)
        out.append(d)
    return out
