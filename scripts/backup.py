#!/usr/bin/env python
"""
SQLite database backup script for BotSalinha.

Creates timestamped backups of the database with optional retention policy.
"""

import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys


def backup_database(
    db_path: Path,
    backup_dir: Path,
    retain_days: int = 7,
) -> Path:
    """
    Create a backup of the SQLite database.

    Args:
        db_path: Path to the database file
        backup_dir: Directory to store backups
        retain_days: Number of days to retain backups

    Returns:
        Path to the created backup file
    """
    if not db_path.exists():
        print(f"❌ Database file not found: {db_path}")
        sys.exit(1)

    # Create backup directory
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate backup filename with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"botsalinha_backup_{timestamp}.db"
    backup_path = backup_dir / backup_filename

    # Use SQLite backup API for consistent backup
    try:
        # Connect to source database
        source = sqlite3.connect(str(db_path))

        # Create backup
        backup = sqlite3.connect(str(backup_path))
        source.backup(backup)

        # Close connections
        backup.close()
        source.close()

        print(f"✅ Backup created: {backup_path}")

    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(1)

    # Clean up old backups
    cleanup_old_backups(backup_dir, retain_days)

    return backup_path


def cleanup_old_backups(backup_dir: Path, retain_days: int) -> None:
    """
    Remove backups older than retain_days.

    Args:
        backup_dir: Directory containing backups
        retain_days: Number of days to retain
    """
    if retain_days <= 0:
        print("📝 Backup retention disabled (retain_days=0)")
        return

    cutoff = datetime.now(timezone.utc).timestamp() - (retain_days * 86400)
    removed = 0

    for backup_file in backup_dir.glob("botsalinha_backup_*.db"):
        if backup_file.stat().st_mtime < cutoff:
            try:
                backup_file.unlink()
                removed += 1
            except Exception as e:
                print(f"⚠️ Failed to remove old backup {backup_file.name}: {e}")

    if removed > 0:
        print(f"🗑️ Removed {removed} old backup(s)")


def list_backups(backup_dir: Path) -> None:
    """
    List all backups in the backup directory.

    Args:
        backup_dir: Directory containing backups
    """
    backups = sorted(backup_dir.glob("botsalinha_backup_*.db"), reverse=True)

    if not backups:
        print("📭 No backups found")
        return

    print(f"\n📦 Backups in {backup_dir}:")
    print("-" * 80)

    total_size = 0
    for backup in backups:
        size_mb = backup.stat().st_size / (1024 * 1024)
        total_size += backup.stat().st_size
        mtime = datetime.fromtimestamp(backup.stat().st_mtime, tz=timezone.utc)
        mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"  {backup.name:50} {mtime_str}  {size_mb:8.2f} MB")

    print("-" * 80)
    print(f"  Total: {len(backups)} backup(s), {total_size / (1024*1024):.2f} MB\n")


def restore_backup(backup_path: Path, db_path: Path) -> None:
    """
    Restore a database from a backup.

    Args:
        backup_path: Path to the backup file
        db_path: Path where database will be restored
    """
    if not backup_path.exists():
        print(f"❌ Backup file not found: {backup_path}")
        sys.exit(1)

    # Confirm restoration
    response = input(
        f"This will REPLACE the current database at {db_path}.\n"
        f"Are you sure? (yes/no): "
    )

    if response.lower() != "yes":
        print("❌ Restoration cancelled")
        sys.exit(0)

    # Create backup of current database before restoring
    if db_path.exists():
        print("📝 Creating backup of current database...")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        pre_restore_backup = db_path.parent / f"botsalinha_prerestore_{timestamp}.db"
        shutil.copy2(db_path, pre_restore_backup)
        print(f"✅ Pre-restore backup saved: {pre_restore_backup}")

    # Restore from backup
    try:
        shutil.copy2(backup_path, db_path)
        print(f"✅ Database restored from: {backup_path}")
    except Exception as e:
        print(f"❌ Restoration failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the backup script."""
    parser = argparse.ArgumentParser(
        description="BotSalinha SQLite database backup tool"
    )
    parser.add_argument(
        "command",
        choices=["backup", "list", "restore"],
        help="Command to execute",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/botsalinha.db"),
        help="Path to the database file (default: data/botsalinha.db)",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path("backups"),
        help="Directory for backups (default: backups)",
    )
    parser.add_argument(
        "--retain-days",
        type=int,
        default=7,
        help="Number of days to retain backups (default: 7, 0 to keep all)",
    )
    parser.add_argument(
        "--restore-from",
        type=Path,
        help="Backup file to restore (required for restore command)",
    )

    args = parser.parse_args()

    if args.command == "backup":
        backup_database(args.db, args.backup_dir, args.retain_days)

    elif args.command == "list":
        list_backups(args.backup_dir)

    elif args.command == "restore":
        if not args.restore_from:
            print("❌ --restore-from is required for restore command")
            sys.exit(1)
        restore_backup(args.restore_from, args.db)


if __name__ == "__main__":
    main()
