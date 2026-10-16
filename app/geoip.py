"""离线 GeoIP 归属（DB-IP Lite，CC BY 4.0）。

库文件放在 GEOIP_DIR（默认 data/），用 tools/fetch_geodb.py 下载。
库缺失或 IP 为私有/保留地址时优雅降级为 ('', '')，不影响主流程。
"""
import ipaddress
import threading
from pathlib import Path
from typing import Optional, Tuple

import app.config as cfg

try:
    import maxminddb
except ImportError:  # 依赖缺失时整体降级
    maxminddb = None


class GeoIPResolver:
    # 支持 DB-IP 与 GeoLite2 两种来源（字段结构兼容），按顺序取第一个存在的库
    CITY_CANDIDATES = ("dbip-city-lite.mmdb", "GeoLite2-City.mmdb")
    ASN_CANDIDATES = ("dbip-asn-lite.mmdb", "GeoLite2-ASN.mmdb")

    def __init__(self, data_dir: Path):
        self._city = self._open(data_dir, self.CITY_CANDIDATES)
        self._asn = self._open(data_dir, self.ASN_CANDIDATES)
        self._lock = threading.Lock()
        self._cache = {}

    @staticmethod
    def _open(data_dir: Path, candidates):
        if maxminddb is None:
            return None
        for name in candidates:
            path = data_dir / name
            if not path.exists():
                continue
            try:
                return maxminddb.open_database(str(path))
            except Exception:
                continue
        return None

    @property
    def city_loaded(self) -> bool:
        return self._city is not None

    @property
    def asn_loaded(self) -> bool:
        return self._asn is not None

    def resolve(self, ip: str) -> Tuple[str, str]:
        """返回 (country_code, asn 描述)。私有/保留地址或库缺失时返回 ('', '')。"""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return "", ""
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
        ):
            return "", ""

        with self._lock:
            hit = self._cache.get(ip)
        if hit is not None:
            return hit

        cc, org = "", ""
        if self._city:
            rec = self._city.get(str(addr)) or {}
            cc = ((rec.get("country") or {}).get("iso_code") or "").upper()
        if self._asn:
            rec = self._asn.get(str(addr)) or {}
            num = rec.get("autonomous_system_number")
            name = rec.get("autonomous_system_organization") or ""
            org = (("AS" + str(num) + " " + name) if num else name).strip()

        with self._lock:
            if len(self._cache) > 8192:
                self._cache.clear()
            self._cache[ip] = (cc, org)
        return cc, org


_resolver: Optional[GeoIPResolver] = None


def get_geoip() -> GeoIPResolver:
    global _resolver
    if _resolver is None:
        _resolver = GeoIPResolver(Path(cfg.GEOIP_DIR))
    return _resolver
