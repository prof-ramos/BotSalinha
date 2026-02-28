"""
Database file guard for BotSalinha.

Runs at startup to:
1. Ensure the ``data/`` directory exists.
2. Create a rolling auto-backup of the existing database (keeps last 5).
3. Verify the database is not corrupt via ``PRAGMA integrity_check``.

Only acts on file-based SQLite databases (skipped for ``:memory:``).
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

_BACKUP_PREFIX = "botsalinha_auto_"
_MAX_BACKUPS = 5


class DatabaseGuard:
    """Protects the SQLite database file at startup.

    Usage::

        guard = DatabaseGuard(db_path=Path("data/botsalinha.db"))
        guard.run()  # call once before the engine initialises tables
    """

    def __init__(
        self,
        db_path: Path,
        backup_dir: Path | None = None,
        max_backups: int = _MAX_BACKUPS,
    ) -> None:
        self._db_path = db_path
        self._backup_dir = backup_dir or (db_path.parent / "backups")
        self._max_backups = max_backups

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute all guard steps.  Safe to call even if the DB doesn't exist yet."""
        self._ensure_data_dir()

        if not self._db_path.exists():
            log.info(
                "db_guard_new_database",
                path=str(self._db_path),
            )
            return

        self._backup()
        self._integrity_check()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_data_dir(self) -> None:
        """Create data/ and backups/ directories if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _backup(self) -> None:
        """Copy the database to the backup directory using SQLite's native backup API."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_path = self._backup_dir / f"{_BACKUP_PREFIX}{timestamp}.db"

        try:
            src = sqlite3.connect(str(self._db_path))
            dst = sqlite3.connect(str(backup_path))
            src.backup(dst)
            dst.close()
            src.close()

            size_kb = backup_path.stat().st_size // 1024
            log.info(
                "db_guard_backup_created",
                backup=str(backup_path),
                size_kb=size_kb,
            )
        except Exception as exc:
            log.warning("db_guard_backup_failed", error=str(exc))
            if backup_path.exists():
                backup_path.unlink(missing_ok=True)
            return

        self._prune_old_backups()

    def _prune_old_backups(self) -> None:
        """Keep only the most recent ``_max_backups`` auto-backups."""
        backups = sorted(
            self._backup_dir.glob(f"{_BACKUP_PREFIX}*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in backups[self._max_backups :]:
            try:
                old.unlink()
                log.debug("db_guard_old_backup_pruned", file=old.name)
            except OSError:
                pass

    def _integrity_check(self) -> None:
        """Run ``PRAGMA integrity_check`` and warn if the database is damaged."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()

            if result and result[0] == "ok":
                log.info("db_guard_integrity_ok", path=str(self._db_path))
            else:
                log.error(
                    "db_guard_integrity_failed",
                    path=str(self._db_path),
                    result=result,
                    hint="Restaure a partir do backup mais recente em data/backups/",
                )
        except Exception as exc:
            log.warning("db_guard_integrity_check_error", error=str(exc))


__all__ = ["DatabaseGuard"]
