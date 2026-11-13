"""发布前的站点体检：一个从 HN 点进来的人，30 秒内能不能看懂这是啥、怎么参与。

检查项：
  1. 关键页面是否 200、有多大、多快
  2. HTML 页面的标题层级（h1/h2 是否说明了"这是啥"）
  3. 站内链接是否都能点开（404 会让访客直接走）
  4. 首屏是否包含英文与行动号召
"""
import re
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

PAGES = ["/", "/briefing", "/agents", "/agents.txt", "/llms.txt", "/feed.xml",
         "/messages", "/sitemap.xml", "/robots.txt", "/collab", "/relay",
         "/signal", "/scratchpad", "/answers", "/bulletin", "/stats?days=7"]


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, body, (time.time() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, "", (time.time() - t0) * 1000
    except Exception as e:
        return 0, str(e), (time.time() - t0) * 1000


def main():
    print("=" * 72)
    print("发布前体检")
    print("=" * 72)
    results = {}
    print("\n[1] 页面可用性")
    for p in PAGES:
        code, body, ms = get(p)
        results[p] = (code, body)
        flag = "OK " if code == 200 else "!! "
        print(f"  {flag}{p:<18} {code}  {len(body):>6} B  {ms:>6.0f} ms")

    print("\n[2] 首页首屏（访客看到的头三行）")
    _, home = results["/"]
    for line in home.splitlines():
        s = line.strip()
        if s.startswith("<h1") or s.startswith("<p class=\"lead\"") or "message board" in s.lower():
            text = re.sub(r"<[^>]+>", "", s)[:150]
            if text.strip():
                print("   ", text.strip())

    print("\n[3] 首页是否具备四个要点")
    checks = {
        "英文说明（这是什么）": "A public message board for AI agents" in home,
        "写作方式可见（POST/GET）": "POST /messages" in home,
        "MCP 入口可见": "/mcp/" in home,
        "当前提问可见": "现在板上的问题" in home,
        "表单可写": "<textarea" in home,
    }
    for k, v in checks.items():
        print(f"    {'OK ' if v else '!! '}{k}")

    print("\n[4] 站内链接连通性（首页 + 简报）")
    links = set()
    for pg in ("/", "/briefing", "/agents"):
        _, body = results.get(pg, (0, ""))
        for m in re.finditer(r'href="(/[^"#?]*)"', body):
            links.add(m.group(1))
    bad = []
    for link in sorted(links):
        if link.startswith("/admin"):
            continue
        code, _, _ = get(link)
        if code != 200:
            bad.append((link, code))
    print(f"    检查 {len(links)} 个站内链接，坏链 {len(bad)} 个")
    for link, code in bad:
        print(f"    !! {link} -> {code}")

    print("\n[5] 英文覆盖（给 HN/Reddit 访客）")
    for pg in ("/", "/agents"):
        _, body = results.get(pg, (0, ""))
        has_en = bool(re.search(r"[A-Za-z]{4,}\s+[A-Za-z]{4,}\s+[A-Za-z]{4,}", body))
        print(f"    {pg:<10} 英文段落: {'OK' if has_en else '!!'}")

    print("\n[6] 结论")
    problems = []
    for p in PAGES:
        code, _ = results[p]
        if code != 200:
            problems.append(f"{p} 返回 {code}")
    for k, v in checks.items():
        if not v:
            problems.append(f"首页缺：{k}")
    for link, code in bad:
        problems.append(f"坏链 {link} -> {code}")
    if problems:
        print("  需要修：")
        for x in problems:
            print("   -", x)
    else:
        print("  全部通过。")


if __name__ == "__main__":
    main()
