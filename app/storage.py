"""存储后端：SQLite（方案 C 本地）与 Supabase（方案 B 免费层）。

按环境变量 STORAGE_BACKEND 选择，接口统一，业务代码无需感知差异。
"""
import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import app.config as cfg
from app.sigverify import normalize_content

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    content TEXT NOT NULL,
    signature TEXT,
    public_key TEXT,
    sig TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    sketch TEXT,
    nonce TEXT,
    links TEXT,
    embedding TEXT,
    nn_embedding TEXT,
    content_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS nonces (
    nonce TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_nonces_expires ON nonces(expires_at);
CREATE TABLE IF NOT EXISTS reads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    ip TEXT NOT NULL,
    user_agent TEXT NOT NULL DEFAULT '',
    ua_family TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    asn TEXT NOT NULL DEFAULT '',
    day TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    first_at TEXT NOT NULL,
    last_at TEXT NOT NULL,
    UNIQUE(path, ip, user_agent, day)
);
CREATE INDEX IF NOT EXISTS idx_reads_last ON reads(last_at);
CREATE TABLE IF NOT EXISTS identities (
    public_key TEXT PRIMARY KEY,
    signature TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bans (
    ip TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS admin_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS blocklist (
    domain TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reads_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archived_at TEXT NOT NULL,
    path TEXT NOT NULL,
    ip TEXT NOT NULL,
    user_agent TEXT NOT NULL DEFAULT '',
    ua_family TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    asn TEXT NOT NULL DEFAULT '',
    day TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    first_at TEXT NOT NULL,
    last_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_archive_day ON reads_archive(day);
CREATE TABLE IF NOT EXISTS sightings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'beacon',
    source_page TEXT NOT NULL DEFAULT '',
    declared_name TEXT NOT NULL DEFAULT '',
    declared_task TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    ua_family TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    asn TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sightings_at ON sightings(at);
"""


class DuplicateError(Exception):
    """内容哈希已存在（去重防刷）。"""


def content_hash(content: str) -> str:
    """归一化（去首尾空白、压缩连续空白、转小写）后取 SHA-256。"""
    return hashlib.sha256(normalize_content(content).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _utc_now() -> str:
    """统一用 UTC ISO 字符串做时间比较，避免时区表示混用导致字符串比较失真。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _dumps_links(links: Optional[List[str]]) -> Optional[str]:
    return json.dumps(links, ensure_ascii=False) if links else None


def _loads_links(value: Optional[str]) -> List[str]:
    if not value:
        return []
    try:
        out = json.loads(value)
        return out if isinstance(out, list) else []
    except (ValueError, TypeError):
        return []


class BaseStorage:
    def list_messages(self, limit: int = 50) -> List[dict]:
        raise NotImplementedError

    def find_by_hash(self, content_hash_value: str) -> Optional[dict]:
        raise NotImplementedError

    def create_message(
        self,
        content: str,
        signature: Optional[str],
        public_key: Optional[str],
        sig: Optional[str],
        verified: bool,
        sketch_value: Optional[str],
        nonce: Optional[str],
        links: Optional[List[str]],
        embedding: Optional[str],
        nn_embedding: Optional[str],
        content_hash_value: str,
    ) -> dict:
        raise NotImplementedError

    def delete_message(self, msg_id: int) -> bool:
        raise NotImplementedError

    def recent_sketches(self, limit: int = 500) -> List[dict]:
        """返回最近的 [{"id": int, "sketch": "hex"}],用于相似度比对。"""
        raise NotImplementedError

    def recent_embeddings(self, limit: int = 500) -> List[dict]:
        """返回最近的 [{"id": int, "embedding": "json"}],用于精确认证。"""
        raise NotImplementedError

    def recent_nn_embeddings(self, limit: int = 100) -> List[dict]:
        """返回最近的 [{"id": int, "nn_embedding": "json数组"}],用于神经网络精确认证。"""
        raise NotImplementedError

    def create_nonce(self, nonce: str, expires_at: str) -> None:
        raise NotImplementedError

    def consume_nonce(self, nonce: str) -> bool:
        """原子地消费一个 nonce：未使用且未过期时置为已用并返回 True。"""
        raise NotImplementedError

    def record_read(
        self, path: str, ip: str, user_agent: str, family: str, country: str, asn: str
    ) -> None:
        raise NotImplementedError

    def list_reads(self, limit: int = 200) -> List[dict]:
        raise NotImplementedError

    def family_stats(self, days: int = 7) -> List[dict]:
        """按 UA 家族聚合访客（用于"谁来了"排行）。"""
        raise NotImplementedError

    def ban_ip(self, ip: str, reason: str) -> None:
        raise NotImplementedError

    def unban_ip(self, ip: str) -> bool:
        raise NotImplementedError

    def is_banned(self, ip: str) -> bool:
        raise NotImplementedError

    def list_bans(self) -> List[dict]:
        raise NotImplementedError

    def log_admin(self, action: str, detail: str) -> None:
        raise NotImplementedError

    def list_admin_log(self, limit: int = 200) -> List[dict]:
        raise NotImplementedError

    def get_identity(self, public_key: str) -> Optional[dict]:
        raise NotImplementedError

    def register_identity(self, public_key: str, signature: Optional[str]) -> None:
        raise NotImplementedError

    def touch_identity(self, public_key: str) -> None:
        raise NotImplementedError

    def delete_identity(self, public_key: str) -> bool:
        raise NotImplementedError

    def list_identities(self) -> List[dict]:
        raise NotImplementedError

    def blocklist_add(self, domain: str, reason: str) -> None:
        raise NotImplementedError

    def blocklist_remove(self, domain: str) -> bool:
        raise NotImplementedError

    def blocklist_all(self) -> List[dict]:
        raise NotImplementedError

    def rotate_reads(self, cutoff_day: str) -> int:
        """把 day < cutoff 的 reads 归档到 reads_archive，返回归档行数。"""
        raise NotImplementedError

    def list_reads_archive(self, limit: int = 200) -> List[dict]:
        raise NotImplementedError

    def add_sighting(
        self,
        kind: str,
        source_page: str,
        declared_name: str,
        declared_task: str,
        notes: str,
        ip: str,
        user_agent: str,
        family: str,
        country: str,
        asn: str,
    ) -> int:
        """记录一次"陷阱命中"（信标登记 / 金丝雀触发）。"""
        raise NotImplementedError

    def list_sightings(self, limit: int = 200) -> List[dict]:
        raise NotImplementedError

    def sighting_stats(self, days: int = 7) -> List[dict]:
        raise NotImplementedError


class SQLiteStorage(BaseStorage):
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def list_messages(self, limit: int = 50) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, content, signature, public_key, sig, verified, nonce, links"
                " FROM messages ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["verified"] = bool(d["verified"])
            d["links"] = _loads_links(d.get("links"))
            out.append(d)
        return out

    def find_by_hash(self, content_hash_value: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, created_at, content, signature, public_key, sig, verified, nonce, links"
                " FROM messages WHERE content_hash = ?",
                (content_hash_value,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["verified"] = bool(d["verified"])
        d["links"] = _loads_links(d.get("links"))
        return d

    def create_message(
        self,
        content: str,
        signature: Optional[str],
        public_key: Optional[str],
        sig: Optional[str],
        verified: bool,
        sketch_value: Optional[str],
        nonce: Optional[str],
        links: Optional[List[str]],
        embedding: Optional[str],
        nn_embedding: Optional[str],
        content_hash_value: str,
    ) -> dict:
        created_at = _now()
        try:
            with self._lock:
                cur = self._conn.execute(
                    "INSERT INTO messages (created_at, content, signature, public_key, sig, verified, sketch, nonce, links, embedding, nn_embedding, content_hash)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        created_at,
                        content,
                        signature,
                        public_key,
                        sig,
                        int(verified),
                        sketch_value,
                        nonce,
                        _dumps_links(links),
                        embedding,
                        nn_embedding,
                        content_hash_value,
                    ),
                )
                self._conn.commit()
                msg_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise DuplicateError("duplicate content") from None
        return {
            "id": msg_id,
            "created_at": created_at,
            "content": content,
            "signature": signature,
            "public_key": public_key,
            "sig": sig,
            "nonce": nonce,
            "links": links or [],
            "verified": bool(verified),
        }

    def delete_message(self, msg_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
            self._conn.commit()
            return cur.rowcount == 1

    def recent_sketches(self, limit: int = 500) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, sketch FROM messages"
                " WHERE sketch IS NOT NULL ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_embeddings(self, limit: int = 500) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, embedding FROM messages"
                " WHERE embedding IS NOT NULL ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_nn_embeddings(self, limit: int = 100) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, nn_embedding FROM messages"
                " WHERE nn_embedding IS NOT NULL ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def create_nonce(self, nonce: str, expires_at: str) -> None:
        with self._lock:
            # 顺带清理过期 nonce，防止表无限膨胀
            self._conn.execute("DELETE FROM nonces WHERE expires_at < ?", (_utc_now(),))
            self._conn.execute(
                "INSERT INTO nonces (nonce, created_at, expires_at) VALUES (?, ?, ?)",
                (nonce, _utc_now(), expires_at),
            )
            self._conn.commit()

    def consume_nonce(self, nonce: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE nonces SET used = 1 WHERE nonce = ? AND used = 0 AND expires_at > ?",
                (nonce, _utc_now()),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def record_read(
        self, path: str, ip: str, user_agent: str, family: str, country: str, asn: str
    ) -> None:
        now = _now()
        day = _utc_day()
        with self._lock:
            self._conn.execute(
                """INSERT INTO reads (path, ip, user_agent, ua_family, country, asn, day, count, first_at, last_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                   ON CONFLICT(path, ip, user_agent, day)
                   DO UPDATE SET count = count + 1, last_at = excluded.last_at""",
                (path, ip, user_agent, family, country, asn, day, now, now),
            )
            self._conn.commit()

    def list_reads(self, limit: int = 200) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT path, ip, user_agent, ua_family, country, asn, day, count, first_at, last_at"
                " FROM reads ORDER BY last_at DESC, count DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def family_stats(self, days: int = 7) -> List[dict]:
        cutoff = (
            datetime.now(timezone.utc).date() - timedelta(days=max(days, 1))
        ).strftime("%Y-%m-%d")
        with self._lock:
            rows = self._conn.execute(
                "SELECT ua_family, COUNT(*) AS records, SUM(count) AS hits,"
                " COUNT(DISTINCT ip) AS unique_ips, MAX(last_at) AS last_seen"
                " FROM reads WHERE day >= ? GROUP BY ua_family ORDER BY hits DESC",
                (cutoff,),
            ).fetchall()
        return [dict(r) for r in rows]

    def ban_ip(self, ip: str, reason: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO bans (ip, created_at, reason) VALUES (?, ?, ?)"
                " ON CONFLICT(ip) DO UPDATE SET reason = excluded.reason",
                (ip, _now(), reason),
            )
            self._conn.commit()

    def unban_ip(self, ip: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM bans WHERE ip = ?", (ip,))
            self._conn.commit()
            return cur.rowcount == 1

    def is_banned(self, ip: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM bans WHERE ip = ? LIMIT 1", (ip,)
            ).fetchone()
        return row is not None

    def list_bans(self) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ip, created_at, reason FROM bans ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def log_admin(self, action: str, detail: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO admin_log (at, action, detail) VALUES (?, ?, ?)",
                (_now(), action, detail),
            )
            self._conn.commit()

    def list_admin_log(self, limit: int = 200) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, at, action, detail FROM admin_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_identity(self, public_key: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT public_key, signature, first_seen, last_seen, message_count"
                " FROM identities WHERE public_key = ?",
                (public_key,),
            ).fetchone()
        return dict(row) if row else None

    def register_identity(self, public_key: str, signature: Optional[str]) -> None:
        now = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO identities (public_key, signature, first_seen, last_seen, message_count)"
                " VALUES (?, ?, ?, ?, 1)"
                " ON CONFLICT(public_key) DO NOTHING",
                (public_key, signature, now, now),
            )
            self._conn.commit()

    def touch_identity(self, public_key: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE identities SET last_seen = ?, message_count = message_count + 1 WHERE public_key = ?",
                (_now(), public_key),
            )
            self._conn.commit()

    def delete_identity(self, public_key: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM identities WHERE public_key = ?", (public_key,)
            )
            self._conn.commit()
            return cur.rowcount == 1

    def list_identities(self) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT public_key, signature, first_seen, last_seen, message_count"
                " FROM identities ORDER BY message_count DESC, last_seen DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def blocklist_add(self, domain: str, reason: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO blocklist (domain, created_at, reason) VALUES (?, ?, ?)"
                " ON CONFLICT(domain) DO UPDATE SET reason = excluded.reason",
                (domain, _now(), reason),
            )
            self._conn.commit()

    def blocklist_remove(self, domain: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM blocklist WHERE domain = ?", (domain,)
            )
            self._conn.commit()
            return cur.rowcount == 1

    def blocklist_all(self) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT domain, created_at, reason FROM blocklist ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def rotate_reads(self, cutoff_day: str) -> int:
        with self._lock:
            archived_at = _now()
            self._conn.execute(
                """INSERT INTO reads_archive
                   (archived_at, path, ip, user_agent, ua_family, country, asn, day, count, first_at, last_at)
                   SELECT ?, path, ip, user_agent, ua_family, country, asn, day, count, first_at, last_at
                   FROM reads WHERE day < ?""",
                (archived_at, cutoff_day),
            )
            cur = self._conn.execute("DELETE FROM reads WHERE day < ?", (cutoff_day,))
            self._conn.commit()
            return cur.rowcount

    def list_reads_archive(self, limit: int = 200) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, archived_at, path, ip, user_agent, ua_family, country, asn, day, count, first_at, last_at"
                " FROM reads_archive ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_sighting(
        self,
        kind: str,
        source_page: str,
        declared_name: str,
        declared_task: str,
        notes: str,
        ip: str,
        user_agent: str,
        family: str,
        country: str,
        asn: str,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO sightings (at, kind, source_page, declared_name, declared_task, notes,"
                " ip, user_agent, ua_family, country, asn) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _now(),
                    kind,
                    source_page,
                    declared_name,
                    declared_task,
                    notes,
                    ip,
                    user_agent,
                    family,
                    country,
                    asn,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def list_sightings(self, limit: int = 200) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, at, kind, source_page, declared_name, declared_task, notes,"
                " ip, user_agent, ua_family, country, asn"
                " FROM sightings ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def sighting_stats(self, days: int = 7) -> List[dict]:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=max(days, 1))
        ).isoformat(timespec="seconds")
        with self._lock:
            rows = self._conn.execute(
                "SELECT kind, source_page, COUNT(*) AS hits, MAX(at) AS last_at"
                " FROM sightings WHERE at >= ? GROUP BY kind, source_page ORDER BY hits DESC",
                (cutoff,),
            ).fetchall()
        return [dict(r) for r in rows]


class SupabaseStorage(BaseStorage):
    def __init__(self, url: str, key: str):
        from supabase import create_client

        # service_role key 可绕过 RLS（服务端内部写入用，防 reads 伪造）；缺省退回 anon key
        self._client = create_client(url, cfg.SUPABASE_SERVICE_KEY or key)

    @staticmethod
    def _norm(row: dict) -> dict:
        """把 datetime 等非 JSON 类型规整成字符串。"""
        out = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                v = v.isoformat()
            out[k] = v
        return out

    def list_messages(self, limit: int = 50) -> List[dict]:
        res = (
            self._client.table("messages")
            .select("id, created_at, content, signature, public_key, sig, verified, nonce, links")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        out = []
        for r in res.data or []:
            d = self._norm(r)
            d["links"] = _loads_links(d.get("links"))
            out.append(d)
        return out

    def find_by_hash(self, content_hash_value: str) -> Optional[dict]:
        res = (
            self._client.table("messages")
            .select("id, created_at, content, signature, public_key, sig, verified, nonce, links")
            .eq("content_hash", content_hash_value)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        d = self._norm(res.data[0])
        d["links"] = _loads_links(d.get("links"))
        return d

    def create_message(
        self,
        content: str,
        signature: Optional[str],
        public_key: Optional[str],
        sig: Optional[str],
        verified: bool,
        sketch_value: Optional[str],
        nonce: Optional[str],
        links: Optional[List[str]],
        embedding: Optional[str],
        nn_embedding: Optional[str],
        content_hash_value: str,
    ) -> dict:
        try:
            res = (
                self._client.table("messages")
                .insert(
                    {
                        "content": content,
                        "signature": signature,
                        "public_key": public_key,
                        "sig": sig,
                        "verified": bool(verified),
                        "sketch": sketch_value,
                        "nonce": nonce,
                        "links": _dumps_links(links),
                        "embedding": embedding,
                        "nn_embedding": nn_embedding,
                        "content_hash": content_hash_value,
                    }
                )
                .execute()
            )
        except Exception as e:
            if "23505" in str(e):  # Postgres unique_violation
                raise DuplicateError("duplicate content") from None
            raise
        if not res.data:
            raise RuntimeError("Supabase insert 失败，请检查表结构与 anon key 权限")
        d = self._norm(res.data[0])
        d["links"] = _loads_links(d.get("links"))
        return d

    def delete_message(self, msg_id: int) -> bool:
        res = self._client.table("messages").delete().eq("id", msg_id).execute()
        return bool(res.data)

    def recent_sketches(self, limit: int = 500) -> List[dict]:
        res = (
            self._client.table("messages")
            .select("id, sketch")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return [{"id": r["id"], "sketch": r["sketch"]} for r in (res.data or []) if r.get("sketch")]

    def recent_embeddings(self, limit: int = 500) -> List[dict]:
        res = (
            self._client.table("messages")
            .select("id, embedding")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return [{"id": r["id"], "embedding": r["embedding"]} for r in (res.data or []) if r.get("embedding")]

    def recent_nn_embeddings(self, limit: int = 100) -> List[dict]:
        res = (
            self._client.table("messages")
            .select("id, nn_embedding")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return [{"id": r["id"], "nn_embedding": r["nn_embedding"]} for r in (res.data or []) if r.get("nn_embedding")]

    def create_nonce(self, nonce: str, expires_at: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        # 顺带清理过期 nonce，防止表无限膨胀
        self._client.table("nonces").delete().lt("expires_at", now).execute()
        self._client.table("nonces").insert({"nonce": nonce, "expires_at": expires_at}).execute()

    def consume_nonce(self, nonce: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        res = (
            self._client.table("nonces")
            .update({"used": True})
            .eq("nonce", nonce)
            .eq("used", False)
            .gt("expires_at", now)
            .execute()
        )
        return bool(res.data)

    def record_read(
        self, path: str, ip: str, user_agent: str, family: str, country: str, asn: str
    ) -> None:
        day = _utc_day()
        res = (
            self._client.table("reads")
            .select("id, count")
            .eq("day", day)
            .eq("path", path)
            .eq("ip", ip)
            .eq("user_agent", user_agent)
            .limit(1)
            .execute()
        )
        if res.data:
            self._client.table("reads").update(
                {"count": int(res.data[0]["count"]) + 1, "last_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", res.data[0]["id"]).execute()
        else:
            self._client.table("reads").insert(
                {
                    "day": day,
                    "path": path,
                    "ip": ip,
                    "user_agent": user_agent,
                    "ua_family": family,
                    "country": country,
                    "asn": asn,
                }
            ).execute()

    def list_reads(self, limit: int = 200) -> List[dict]:
        res = (
            self._client.table("reads")
            .select("path, ip, user_agent, ua_family, country, asn, day, count, first_at, last_at")
            .order("last_at", desc=True)
            .order("count", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._norm(r) for r in (res.data or [])]

    def family_stats(self, days: int = 7) -> List[dict]:
        cutoff = (
            datetime.now(timezone.utc).date() - timedelta(days=max(days, 1))
        ).strftime("%Y-%m-%d")
        res = (
            self._client.table("reads")
            .select("ua_family, ip, count, last_at")
            .gte("day", cutoff)
            .execute()
        )
        agg = {}
        for r in res.data or []:
            fam = r.get("ua_family") or ""
            a = agg.setdefault(
                fam, {"ua_family": fam, "records": 0, "hits": 0, "_ips": set(), "last_seen": ""}
            )
            a["records"] += 1
            a["hits"] += int(r.get("count") or 0)
            a["_ips"].add(r.get("ip"))
            a["last_seen"] = max(a["last_seen"], r.get("last_at") or "")
        out = []
        for a in agg.values():
            a["unique_ips"] = len(a.pop("_ips"))
            out.append(self._norm(a))
        out.sort(key=lambda x: x["hits"], reverse=True)
        return out

    def ban_ip(self, ip: str, reason: str) -> None:
        self._client.table("bans").upsert(
            {"ip": ip, "reason": reason}, on_conflict="ip"
        ).execute()

    def unban_ip(self, ip: str) -> bool:
        res = self._client.table("bans").delete().eq("ip", ip).execute()
        return bool(res.data)

    def is_banned(self, ip: str) -> bool:
        res = self._client.table("bans").select("ip").eq("ip", ip).limit(1).execute()
        return bool(res.data)

    def list_bans(self) -> List[dict]:
        res = self._client.table("bans").select("ip, created_at, reason").order("created_at", desc=True).execute()
        return [self._norm(r) for r in (res.data or [])]

    def log_admin(self, action: str, detail: str) -> None:
        self._client.table("admin_log").insert({"action": action, "detail": detail}).execute()

    def list_admin_log(self, limit: int = 200) -> List[dict]:
        res = (
            self._client.table("admin_log")
            .select("id, at, action, detail")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._norm(r) for r in (res.data or [])]

    def get_identity(self, public_key: str) -> Optional[dict]:
        res = (
            self._client.table("identities")
            .select("public_key, signature, first_seen, last_seen, message_count")
            .eq("public_key", public_key)
            .limit(1)
            .execute()
        )
        return self._norm(res.data[0]) if res.data else None

    def register_identity(self, public_key: str, signature: Optional[str]) -> None:
        self._client.table("identities").insert(
            {"public_key": public_key, "signature": signature}
        ).execute()

    def touch_identity(self, public_key: str) -> None:
        row = self.get_identity(public_key)
        if row:
            self._client.table("identities").update(
                {
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "message_count": int(row.get("message_count") or 0) + 1,
                }
            ).eq("public_key", public_key).execute()

    def delete_identity(self, public_key: str) -> bool:
        res = self._client.table("identities").delete().eq("public_key", public_key).execute()
        return bool(res.data)

    def list_identities(self) -> List[dict]:
        res = (
            self._client.table("identities")
            .select("public_key, signature, first_seen, last_seen, message_count")
            .order("message_count", desc=True)
            .execute()
        )
        return [self._norm(r) for r in (res.data or [])]

    def blocklist_add(self, domain: str, reason: str) -> None:
        self._client.table("blocklist").upsert(
            {"domain": domain, "reason": reason}, on_conflict="domain"
        ).execute()

    def blocklist_remove(self, domain: str) -> bool:
        res = self._client.table("blocklist").delete().eq("domain", domain).execute()
        return bool(res.data)

    def blocklist_all(self) -> List[dict]:
        res = self._client.table("blocklist").select("domain, created_at, reason").order("created_at", desc=True).execute()
        return [self._norm(r) for r in (res.data or [])]

    def rotate_reads(self, cutoff_day: str) -> int:
        old = (
            self._client.table("reads")
            .select("path, ip, user_agent, ua_family, country, asn, day, count, first_at, last_at")
            .lt("day", cutoff_day)
            .execute()
        )
        rows = old.data or []
        if rows:
            self._client.table("reads_archive").insert(rows).execute()
            self._client.table("reads").delete().lt("day", cutoff_day).execute()
        return len(rows)

    def list_reads_archive(self, limit: int = 200) -> List[dict]:
        res = (
            self._client.table("reads_archive")
            .select("id, archived_at, path, ip, user_agent, ua_family, country, asn, day, count, first_at, last_at")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._norm(r) for r in (res.data or [])]

    def add_sighting(
        self,
        kind: str,
        source_page: str,
        declared_name: str,
        declared_task: str,
        notes: str,
        ip: str,
        user_agent: str,
        family: str,
        country: str,
        asn: str,
    ) -> int:
        res = (
            self._client.table("sightings")
            .insert(
                {
                    "kind": kind,
                    "source_page": source_page,
                    "declared_name": declared_name,
                    "declared_task": declared_task,
                    "notes": notes,
                    "ip": ip,
                    "user_agent": user_agent,
                    "ua_family": family,
                    "country": country,
                    "asn": asn,
                }
            )
            .execute()
        )
        return int(res.data[0]["id"]) if res.data else 0

    def list_sightings(self, limit: int = 200) -> List[dict]:
        res = (
            self._client.table("sightings")
            .select("id, at, kind, source_page, declared_name, declared_task, notes, ip, user_agent, ua_family, country, asn")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._norm(r) for r in (res.data or [])]

    def sighting_stats(self, days: int = 7) -> List[dict]:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=max(days, 1))
        ).isoformat(timespec="seconds")
        res = (
            self._client.table("sightings")
            .select("kind, source_page, at")
            .gte("at", cutoff)
            .execute()
        )
        agg: dict = {}
        for r in res.data or []:
            key = (r.get("kind") or "", r.get("source_page") or "")
            a = agg.setdefault(key, {"kind": key[0], "source_page": key[1], "hits": 0, "last_at": ""})
            a["hits"] += 1
            a["last_at"] = max(a["last_at"], r.get("at") or "")
        out = list(agg.values())
        out.sort(key=lambda x: x["hits"], reverse=True)
        return [self._norm(r) for r in out]


_storage: Optional[BaseStorage] = None


def get_storage() -> BaseStorage:
    global _storage
    if _storage is None:
        if cfg.STORAGE_BACKEND == "supabase":
            if not cfg.SUPABASE_URL or not cfg.SUPABASE_KEY:
                raise RuntimeError(
                    "STORAGE_BACKEND=supabase 需要同时设置 SUPABASE_URL 与 SUPABASE_KEY"
                )
            _storage = SupabaseStorage(cfg.SUPABASE_URL, cfg.SUPABASE_KEY)
        else:
            _storage = SQLiteStorage(cfg.SQLITE_PATH)
    return _storage
