"""集中读取环境变量，项目内统一从这里取配置。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# 存储后端：sqlite（方案 C 本地）或 supabase（方案 B 免费层）
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "sqlite").strip().lower()
SQLITE_PATH = os.getenv("SQLITE_PATH", str(BASE_DIR / "data" / "messages.db"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
# 可选：service_role key（服务端内部写入用，可绕过 RLS、防 reads 伪造；留空用 anon key）
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

# 读取留痕：记录 /、/messages、/llms.txt 的访问（按 天+路径+IP+UA 聚合）
LOG_READS = os.getenv("LOG_READS", "1").strip().lower() in ("1", "true", "yes", "on")

# GeoIP 归属：离线库缺失时自动降级为空；用 tools/fetch_geodb.py 下载
GEOIP_ENABLED = os.getenv("GEOIP_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
GEOIP_DIR = os.getenv("GEOIP_DIR", str(BASE_DIR / "data"))

# 写入限流：每来源 IP 每个窗口内最多多少次
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# 签名 nonce 时效（防重放）：POST /challenge 签发的 nonce 超过该秒数即失效
NONCE_TTL_SECONDS = int(os.getenv("NONCE_TTL_SECONDS", "300"))

# 相似度去重（字符 bigram MinHash，Jaccard 估计；实测灌水改写 >= 0.50、无关文本 <= 0.15）
SIM_ENABLED = os.getenv("SIM_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", "0.35"))
SIM_LOOKBACK = int(os.getenv("SIM_LOOKBACK", "500"))
SIM_MIN_LEN = int(os.getenv("SIM_MIN_LEN", "12"))

# Embedding 精确认证层（字符 n-gram 词频向量 + 余弦）：
# MinHash Jaccard >= EMBED_PREFILTER 的候选，再做余弦确认 >= EMBED_THRESHOLD 判重
EMBED_ENABLED = os.getenv("EMBED_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
EMBED_THRESHOLD = float(os.getenv("EMBED_THRESHOLD", "0.4"))
EMBED_PREFILTER = float(os.getenv("EMBED_PREFILTER", "0.10"))
EMBED_MAX_FEATURES = int(os.getenv("EMBED_MAX_FEATURES", "256"))

# 域名信誉：留言外链命中本地黑名单（含子域名）即拒绝
DOMAIN_REP_ENABLED = os.getenv("DOMAIN_REP_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")

# 管理白名单：逗号分隔的 IP 或 CIDR；留空 = 不限 IP（仅令牌）
ADMIN_ALLOWED_IPS = [s.strip() for s in os.getenv("ADMIN_ALLOWED_IPS", "").split(",") if s.strip()]

# 是否信任代理头（X-Forwarded-For / X-Real-Client-IP）。
#   1（默认，部署在 ngrok / cloudflared 后面）= 用代理写入的来源 IP
#   0（直接暴露端口，无代理）= 忽略这些头，只用 TCP 对端地址
# 说明：XFF 的第一段是客户端可伪造的，取最后一段才能防伪造；若前置了多层代理需另行调整。
TRUST_PROXY = os.getenv("TRUST_PROXY", "1").strip().lower() in ("1", "true", "yes", "on")

# 可信来源 IP 头（大小写不敏感）。ngrok traffic policy（tools/ngrok-policy.yml）会在边缘
# 注入这个头并覆盖客户端伪造值，因此它比 X-Forwarded-For 可靠得多。
# 客户端同名头会与注入值形成重复头，解析时取最后一条。
TRUSTED_IP_HEADER = os.getenv("TRUSTED_IP_HEADER", "x-real-client-ip").strip().lower()

# 读取留痕轮转：超过 N 天的 reads 行归档到 reads_archive
READS_RETENTION_DAYS = int(os.getenv("READS_RETENTION_DAYS", "90"))

# 公开视图的访客信息强度（原始 IP / 完整 UA 永远只在 /admin/* 可见）：
#   network = 公开网段（101.71.*.*）+ 完整 UA，便于公开观测
#   hidden  = 公开视图不返回任何 IP 与原始 UA，只留 UA 家族 / 国家 / ASN（访客隐私优先）
IP_PUBLIC_MODE = os.getenv("IP_PUBLIC_MODE", "network").strip().lower()
if IP_PUBLIC_MODE not in ("network", "hidden"):
    IP_PUBLIC_MODE = "network"

# 神经网络 embedding（可选增强层）：fastembed 不可用/模型缺失时自动回退字符 n-gram
NN_EMBED_ENABLED = os.getenv("NN_EMBED_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
NN_EMBED_MODEL = os.getenv("NN_EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
NN_EMBED_THRESHOLD = float(os.getenv("NN_EMBED_THRESHOLD", "0.85"))
NN_EMBED_LOOKBACK = int(os.getenv("NN_EMBED_LOOKBACK", "100"))

# 实时域名信誉 API（URLhaus 免密钥 + 可选 VirusTotal）
REP_API_ENABLED = os.getenv("REP_API_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
REP_API_TIMEOUT = int(os.getenv("REP_API_TIMEOUT", "5"))
VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "").strip()

# 管理双因子：设置 base32 TOTP 密钥后，管理请求需带 X-Admin-TOTP 头
ADMIN_TOTP_SECRET = os.getenv("ADMIN_TOTP_SECRET", "").strip()

# 远程 MCP 端点：装了 mcp SDK 时在 /mcp 暴露 streamable HTTP，agent 可直接连站点 URL
MCP_HTTP_ENABLED = os.getenv("MCP_HTTP_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
# MCP 工具回调自身 API 用的地址（留空则用 PUBLIC_BASE_URL 或 http://127.0.0.1:8000）
MCP_SELF_URL = os.getenv("MCP_SELF_URL", "").strip().rstrip("/")

MAX_CONTENT_LEN = 4000

# 管理令牌：设置后启用 /admin/* 端点（请求头 X-Admin-Token）
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

# 对外公开地址（用于 llms.txt 生成绝对链接；留空则使用请求的 Host）
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")

# 陷阱（诱饵页 + 提示注入蜜罐 + 金丝雀令牌）
TRAP_ENABLED = os.getenv("TRAP_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
# 金丝雀令牌派生密钥：换掉它会让所有旧令牌失效（用于观测"内容被跨站搬运"）
TRAP_CANARY_SEED = os.getenv("TRAP_CANARY_SEED", "").strip() or ADMIN_TOKEN or "deaddrop-default-seed"
# 信标端点限流（防被刷爆 sightings 表）
TRAP_BEACON_RATE_MAX = int(os.getenv("TRAP_BEACON_RATE_MAX", "30"))
TRAP_BEACON_RATE_WINDOW = int(os.getenv("TRAP_BEACON_RATE_WINDOW", "60"))
