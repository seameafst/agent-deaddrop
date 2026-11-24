"""MCP 调用计数。

为什么要有这个模块（2026-11-24）：
    之前判定里写「MCP 工具调用 = 0」，但站点**从来没有记录过任何 MCP 请求**——
    `reads` 表里连 `/mcp` 路径都没有。那个 0 只能从 Glama 后台看，
    属于「我没验证过的数字」，不能拿来做结论。

    所以现在自己数：每个 tools/call 落一行，包含工具名、成功与否、客户端名。
    有 IP 也不存 IP——只存客户端声明的名字，避免又造一个需要脱敏的表。

用法：
    from app import mcp_stats
    mcp_stats.record("tools/call", tool="read_messages", ok=True, client="glama")
    mcp_stats.summary()      # {'total': 3, 'by_tool': {...}, 'since': '...'}
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

import app.config as cfg

_MAX_CLIENT = 60


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(cfg.SQLITE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS mcp_calls (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               at TEXT NOT NULL,
               day TEXT NOT NULL DEFAULT '',
               method TEXT NOT NULL DEFAULT '',
               tool TEXT NOT NULL DEFAULT '',
               ok INTEGER NOT NULL DEFAULT 1,
               client TEXT NOT NULL DEFAULT '',
               selftest INTEGER NOT NULL DEFAULT 0
           )"""
    )
    # 旧表（11-24 早些时候建的）没有 selftest 列，补上
    cols = {r[1] for r in conn.execute("PRAGMA table_info(mcp_calls)")}
    if "selftest" not in cols:
        try:
            conn.execute("ALTER TABLE mcp_calls ADD COLUMN selftest INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                "UPDATE mcp_calls SET selftest = 1 "
                "WHERE LOWER(client) LIKE '%selftest%'"
            )
        except Exception:
            pass
    return conn


def record(method: str, tool: str = "", ok: bool = True, client: str = "") -> None:
    """记一次 MCP 调用。绝不抛异常——统计失败不能影响工具本身。

    selftest 标记：客户端声明名里含 `selftest`（我自己测的）就标 1。
    这样判定里能分开「我自己测了几次」和「外部真的调了几次」，
    不至于用自己的测试数据冒充外部兴趣。
    """
    try:
        now = datetime.now(timezone.utc)
        is_self = 1 if "selftest" in (client or "").lower() else 0
        conn = _conn()
        try:
            conn.execute(
                "INSERT INTO mcp_calls (at, day, method, tool, ok, client, selftest) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    now.isoformat(timespec="seconds"),
                    now.date().isoformat(),
                    (method or "")[:40],
                    (tool or "")[:60],
                    1 if ok else 0,
                    (client or "")[:_MAX_CLIENT],
                    is_self,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def summary(limit_days: Optional[int] = None) -> dict:
    """调用汇总：总数、按工具分布、按天分布、首次记录时间。"""
    try:
        conn = _conn()
        conn.row_factory = sqlite3.Row
        try:
            where = ""
            params: tuple = ()
            if limit_days:
                where = "WHERE at >= datetime('now', ?)"
                params = (f"-{int(limit_days)} days",)
            total = conn.execute(f"SELECT COUNT(*) c FROM mcp_calls {where}", params).fetchone()["c"]
            by_tool = {
                (r["tool"] or "(initialize)"): r["c"]
                for r in conn.execute(
                    f"SELECT tool, COUNT(*) c FROM mcp_calls {where} GROUP BY tool ORDER BY c DESC",
                    params,
                )
            }
            by_day = {
                r["day"]: r["c"]
                for r in conn.execute(
                    f"SELECT day, COUNT(*) c FROM mcp_calls {where} GROUP BY day ORDER BY day DESC LIMIT 14",
                    params,
                )
            }
            first = conn.execute("SELECT MIN(at) a FROM mcp_calls").fetchone()["a"]
            selftest = conn.execute(
                f"SELECT COUNT(*) c FROM mcp_calls {where}"
                + (" AND " if where else "WHERE ")
                + "selftest = 1".replace("selftest", "COALESCE(selftest,0)"),
                params,
            ).fetchone()["c"]
            return {
                "total": total,
                "selftest_total": selftest,
                "external_total": total - selftest,
                "by_tool": by_tool,
                "by_day": by_day,
                "first_recorded_at": first or "",
                "note": "selftest 按 clientInfo.name 里出现 selftest 判定；external_total 才是真实外部调用",
            }
        finally:
            conn.close()
    except Exception as e:
        return {"total": 0, "by_tool": {}, "by_day": {}, "first_recorded_at": "", "error": str(e)[:120]}
