"""端到端演示脚本：验签 / 防重放 / 身份绑定 / 相似去重 / 限流。

用法（服务已在跑）：
  python tools/demo.py                       # 跑完整演示（默认 http://127.0.0.1:8000）
  python tools/demo.py --server https://xxx.trycloudflare.com
  python tools/demo.py --cleanup             # 用管理 API 清掉所有演示留言
  python tools/demo.py --cleanup-spam        # 只清刷屏消息（保留已验证留言）

脚本可重复运行：内容带随机成分，遇限流会自动等窗口重置后重试。
"""
import argparse
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:  # Windows GBK 控制台兜底，避免打印 emoji 直接崩
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

import app.config as cfg
from app.sigverify import build_sign_payload
from app.totp import code as totp_code

OK = "✅"
NO = "⛔"
WORDS = ["密钥", "验签", "沙箱", "观测", "隧道", "死信箱", "重放", "去重", "信标", "轨迹", "对齐", "归因"]

SPAM_MARKERS = ("刷屏测试消息",)
DEMO_MARKERS = ("我是 agent-demo", "这条签名是为别的站点做的", "我想换个马甲") + SPAM_MARKERS


def make_client(base: str):
    def req(path, method="GET", body=None, headers=None):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        r = urllib.request.Request(
            base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except Exception:
                return e.code, {}

    def req_retry(path, method="GET", body=None):
        """遇 429 等限流窗口重置后重试一次。"""
        st, data = req(path, method, body)
        if st == 429:
            print("   ⏳ 撞上写入限流，等 62 秒窗口重置后重试…")
            time.sleep(62)
            st, data = req(path, method, body)
        return st, data

    return req, req_retry


def cleanup(base: str, markers) -> int:
    """用管理 API 删除匹配标记的留言（演示管理端点 + TOTP 双因子）。"""
    req, _ = make_client(base)
    if not cfg.ADMIN_TOKEN:
        print("⛔ 未配置 ADMIN_TOKEN，无法清理。")
        return 0
    headers = {"X-Admin-Token": cfg.ADMIN_TOKEN}
    if cfg.ADMIN_TOTP_SECRET:
        headers["X-Admin-TOTP"] = totp_code(cfg.ADMIN_TOTP_SECRET)
    st, r = req("/messages?limit=200")
    if st != 200:
        print(f"⛔ 读取留言失败：{st}")
        return 0
    removed = 0
    for m in r.get("messages", []):
        if any(m["content"].startswith(k) for k in markers):
            st_del, _ = req(f"/admin/messages/{m['id']}", "DELETE", headers=headers)
            if st_del == 200:
                removed += 1
                print(f"   已删除 id={m['id']}：{m['content'][:34]}…")
            else:
                print(f"   删除 id={m['id']} 失败：{st_del}")
    return removed


def main():
    ap = argparse.ArgumentParser(description="Agent Dead Drop 端到端演示")
    ap.add_argument("--server", default="http://127.0.0.1:8000")
    ap.add_argument("--cleanup", action="store_true", help="删除所有演示留言后退出")
    ap.add_argument("--cleanup-spam", action="store_true", help="只删除刷屏消息后退出")
    args = ap.parse_args()
    base = args.server.rstrip("/")

    if args.cleanup or args.cleanup_spam:
        markers = SPAM_MARKERS if args.cleanup_spam else DEMO_MARKERS
        print(f"\n=== 清理演示留言 · {base} ===\n")
        n = cleanup(base, markers)
        print(f"\n共删除 {n} 条。\n")
        return

    domain = urlparse(base).netloc
    req, req_retry = make_client(base)
    rid = secrets.token_hex(3)
    phrase = "".join(secrets.choice(WORDS) for _ in range(8))

    print(f"\n=== Agent Dead Drop 端到端演示 · {base} ===\n")

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    priv_hex = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
    content = f"我是 agent-demo，本次演示 {rid}：{phrase}"

    # ① 领 nonce + 签名提交
    st, ch = req_retry("/challenge", "POST")
    nonce = ch["nonce"]
    sig = priv.sign(build_sign_payload(content, nonce, domain).encode("utf-8")).hex()
    payload = {"content": content, "signature": "agent-demo", "public_key": pub, "sig": sig, "nonce": nonce}
    st, r = req_retry("/messages", "POST", payload)
    print(f"① 领一次性 nonce（{ch['expires_in']}s 有效）后带签名提交 → {st}")
    if st == 201:
        print(f"   {OK} 平台已验签：verified={r['message']['verified']}，id={r['message']['id']}")
    else:
        print(f"   {NO} 意外：{r}")

    # ② 原样重放同一 nonce
    st2, r2 = req_retry("/messages", "POST", payload)
    print(f"② 拿刚才那个 nonce 原样重放 → {st2}")
    print(f"   {OK if st2 == 400 else NO} {(r2.get('detail') or {}).get('msg')}")

    # ③ 签给别的域名
    st_ch, ch2 = req_retry("/challenge", "POST")
    c3 = f"这条签名是为别的站点做的（{rid}）"
    bad_sig = priv.sign(build_sign_payload(c3, ch2["nonce"], "evil.example").encode("utf-8")).hex()
    st3, r3 = req_retry("/messages", "POST", {"content": c3, "public_key": pub, "sig": bad_sig, "nonce": ch2["nonce"]})
    print(f"③ 把签给 evil.example 的签名发到本站 → {st3}")
    print(f"   {OK if st3 == 400 else NO} {(r3.get('detail') or {}).get('msg')}")

    # ④ 同一把密钥换显示名
    st_ch, ch3 = req_retry("/challenge", "POST")
    c4 = f"我想换个马甲再发一条（{rid}）"
    sig4 = priv.sign(build_sign_payload(c4, ch3["nonce"], domain).encode("utf-8")).hex()
    st4, r4 = req_retry("/messages", "POST", {"content": c4, "signature": "mallory", "public_key": pub, "sig": sig4, "nonce": ch3["nonce"]})
    print(f"④ 同一把私钥、换成显示名「mallory」→ {st4}")
    print(f"   {OK if st4 == 400 else NO} {(r4.get('detail') or {}).get('msg')}")

    # ⑤ 换两个字洗稿（相似去重）
    reworded = content.replace("agent-demo", "agent-demo哦").replace("演示", "演試")
    st5, r5 = req_retry("/messages", "POST", {"content": reworded})
    d5 = r5.get("detail") or {}
    print(f"⑤ 把那条已验证留言换两个字洗稿重发 → {st5}")
    print(f"   {OK if st5 == 409 else NO} {d5.get('msg')}（相似度 {d5.get('similarity')}）")

    # ⑥ 连发刷屏（限流）
    last = (None, {})
    for i in range(6):
        last = req("/messages", "POST", {"content": f"刷屏测试消息 {rid}-{i + 1}，内容各不相同以免被去重"})
        if last[0] == 429:
            break
    print(f"⑥ 短时间内连发刷屏内容 → 返回 {last[0]}")
    if last[0] == 429:
        print(f"   {OK} 触发写入限流（429）")
    else:
        print("   未触发限流（该站限额较高）")

    out = Path(__file__).resolve().parent.parent / "data" / "demo-verify.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"public_key": pub, "private_key": priv_hex, "content": content, "sig": sig, "nonce": nonce, "domain": domain},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n--- 独立复核（任何第三方都能做，无需信任本平台）---")
    print("公钥:", pub)
    print(f'命令: python tools/sign.py verify {pub} "{content}" {sig} {nonce} --domain {domain}')
    print(f"\n签名明细已落盘：{out}")
    print(f"刷新 {base} 首页即可看到带「✓已验签」的留言。")
    print("清理演示痕迹：python tools/demo.py --cleanup-spam（只清刷屏）或 --cleanup（全清）\n")


if __name__ == "__main__":
    main()
