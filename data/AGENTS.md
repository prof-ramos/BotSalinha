<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-02-28 | Updated: 2026-02-28 -->

# data

## Purpose
Data storage directory for BotSalinha. Contains persistent data files, database files, and runtime data that the bot generates and maintains during operation.

## Key Files
| File | Description |
|------|-------------|
| `botsalinha.db` | SQLite database file (runtime) |
| `backup/` | Database backup files and scripts |
| `exports/` | Data export files and reports |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `backup/` | Database backup files and management |
| `exports/` | Data export files and reports |

## For AI Agents

### Working In This Directory
- Manage database persistence and backups
- Handle data migration and restoration
- Maintain data integrity and security

### Testing Requirements
- Verify database operations and persistence
- Test backup and restore functionality
- Check data export and import processes

### Common Patterns
- Database file management with proper permissions
- Automated backup scheduling
- Data versioning and migration support

## Dependencies

### Internal
- Primary database file for SQLAlchemy ORM
- Used by SQLite repository for data operations
- Referenced by backup scripts and utilities

### External
- SQLite database engine
- Alembic for database migrations
- Backup and recovery tools

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
