"""下载离线 GeoIP 库到 data/，无需账号。

来源优先级：DB-IP Lite（CC BY 4.0，首选）→ P3TERX GeoLite2 镜像（GitHub，兜底）。
两种来源的 mmdb 字段结构兼容（country.iso_code / autonomous_system_*），读取器通用。
用法：python tools/fetch_geodb.py
"""
import argparse
import gzip
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# DB-IP 免费档是 gzip 压缩（.mmdb.gz）；P3TERX GeoLite2 镜像为裸 .mmdb
DBIP_CITY = ("https://download.db-ip.com/free/dbip-city-lite-{y}-{m}.mmdb.gz", True)
DBIP_ASN = ("https://download.db-ip.com/free/dbip-asn-lite-{y}-{m}.mmdb.gz", True)
GEOLITE_CITY = (
    "https://github.com/P3TERX/GeoLite.mmdb/releases/download/{y}.{m}/GeoLite2-City.mmdb",
    False,
)
GEOLITE_ASN = (
    "https://github.com/P3TERX/GeoLite.mmdb/releases/download/{y}.{m}/GeoLite2-ASN.mmdb",
    False,
)


def month_seq():
    """从本月起往前回退，最多试 7 个月（找最近一次月更）。"""
    y, m = date.today().year, date.today().month
    for _ in range(7):
        yield y, m
        m -= 1
        if m == 0:
            m = 12
            y -= 1


def download(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def try_source(dest: Path, url_tpl: str, is_gz: bool) -> bool:
    for y, m in month_seq():
        url = url_tpl.format(y=y, m=f"{m:02d}")
        print(f"尝试 {url} …")
        try:
            data = download(url)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}，试上一个月…")
            continue
        except Exception as e:
            print(f"  失败：{e}，试上一个月…")
            continue
        if is_gz:
            data = gzip.decompress(data)
        dest.write_bytes(data)
        print(f"  已保存 {dest}（{len(data) / 1e6:.1f} MB）")
        return True
    return False


def fetch(dest_dir: Path, out_name: str, sources) -> None:
    dest = dest_dir / out_name
    for url_tpl, is_gz in sources:
        if try_source(dest, url_tpl, is_gz):
            return
        print("  换下一个来源…")
    print(f"!! {out_name} 全部来源失败，请检查网络后重试。")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="下载离线 GeoIP 库到本地")
    ap.add_argument(
        "--dir",
        default=str(Path(__file__).resolve().parent.parent / "data"),
        help="保存目录（默认项目 data/）",
    )
    args = ap.parse_args()

    dest_dir = Path(args.dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    fetch(dest_dir, "dbip-city-lite.mmdb", [DBIP_CITY, GEOLITE_CITY])
    fetch(dest_dir, "dbip-asn-lite.mmdb", [DBIP_ASN, GEOLITE_ASN])

    print("完成。重启服务后 /health 会显示 geoip_city / geoip_asn 状态。")


if __name__ == "__main__":
    main()
