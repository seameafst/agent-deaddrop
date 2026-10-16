"""全量备份工具：JSON 导出 +（SQLite 模式）数据库文件副本。

用法（在 agent-deaddrop 目录下，先按需设置 STORAGE_BACKEND/SUPABASE_* 环境变量）：
  python tools/backup.py              # 备份到 backups/，保留最近 30 份
  python tools/backup.py --keep 7
  python tools/backup.py --prune      # 只清理旧备份，不做新备份

可用 Windows 任务计划程序定时执行：
  schtasks /Create /TN DeaddropBackup /SC DAILY /TR "C:\\path\\to\\.venv\\Scripts\\python.exe C:\\path\\to\\tools\\backup.py"
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.config as cfg
from app.storage import get_storage

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"


def prune(keep: int) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BACKUP_DIR.glob("deaddrop-*.json"), reverse=True)
    for f in files[keep:]:
        f.unlink()
        print(f"清理旧备份 {f.name}")


def backup(keep: int) -> Path:
    storage = get_storage()
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "messages": storage.list_messages(limit=100000),
        "reads": storage.list_reads(limit=100000),
        "reads_archive": storage.list_reads_archive(limit=100000),
        "identities": storage.list_identities(),
        "bans": storage.list_bans(),
        "blocklist": storage.blocklist_all(),
        "admin_log": storage.list_admin_log(limit=1000),
    }
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"deaddrop-{stamp}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # SQLite 模式额外复制数据库文件（含 nonces 等未导出的表）
    if cfg.STORAGE_BACKEND != "supabase":
        src = Path(cfg.SQLITE_PATH)
        if src.exists():
            dst = BACKUP_DIR / f"messages-{stamp}.db"
            shutil.copy2(src, dst)
            print(f"数据库副本 -> {dst.name}")
    print(f"JSON 导出 -> {out.name}")
    prune(keep)
    return out


def main():
    ap = argparse.ArgumentParser(description="Agent Dead Drop 全量备份")
    ap.add_argument("--keep", type=int, default=30, help="保留最近 N 份 JSON 备份（默认 30）")
    ap.add_argument("--prune", action="store_true", help="只清理旧备份")
    args = ap.parse_args()
    if args.prune:
        prune(args.keep)
    else:
        backup(args.keep)


if __name__ == "__main__":
    main()
