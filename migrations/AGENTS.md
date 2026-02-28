# AGENTS.md — Database Migrations

Parent reference: ../AGENTS.md (root)

## Context

`migrations/` contains Alembic database migration scripts for managing schema changes in the BotSalinha project. The database layer uses SQLite with SQLAlchemy async ORM and Alembic for version control.

## Key Files

| File | Purpose |
| --- | --- |
| `alembic.ini` | Alembic configuration file - paths, database URL, template settings |
| `env.py` | Migration environment setup - SQLAlchemy engine, connection handling, hooks |
| `script.py.mako` | Template for generating new migration files |
| `versions/` | Individual migration files - auto-generated or manually created |

**Note**: The migration setup uses `script_location = migrations` in `alembic.ini`, which means the migration files are in the same directory as the configuration.

## Directory Structure

```text
migrations/
├── alembic.ini                    # Alembic configuration
├── env.py                       # Migration environment setup
├── script.py.mako               # Migration file template
└── versions/                    # Migration history (auto-generated)
    ├── 001_initial_migration.py  # Example: First migration
    ├── 002_add_user_preferences.py # Example: New table
    └── ...
```

## Common Commands

### Creating Migrations

```bash
# Auto-generate migration after ORM model changes
uv run alembic revision --autogenerate -m "description"

# Create empty migration file (for custom SQL)
uv run alembic revision -m "description"
```

**Note:** `--autogenerate` detects changes in `src/models/` and creates upgrade/downgrade operations automatically.

### Applying Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Apply specific migration by ID
uv run alembic upgrade <migration_id>

# Apply to specific revision
uv run alembic upgrade <revision_number>
```

### Reverting Migrations

```bash
# Revert last migration (creates downgrade operation)
uv run alembic downgrade -1

# Revert to specific version
uv run alembic downgrade <migration_id>

# Revert to base (empty database)
uv run alembic downgrade base
```

### Checking Migration Status

```bash
# Show current migration status
uv run alembic current

# Show migration history
uv run alembic history

# Check if upgrade/downgrade is needed
uv run alembic current --verbose
```

## Migration Workflow

### 1. Modify ORM Models

Change SQLAlchemy models in `src/models/`:

```python
# src/models/conversation.py
class ConversationORM(Base):
    __tablename__ = "conversations"

    # New field added
    user_preferences = Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User preferences JSON"
    )
```

### 2. Create Migration

```bash
uv run alembic revision --autogenerate -m "Add user_preferences field"
```

This generates:
- `upgrade()` - Add the column to existing tables
- `downgrade()` - Remove the column (safe)

### 3. Review Migration File

Always check generated migrations before applying:

```python
def upgrade() -> None:
    # Add user_preferences column to conversations table
    op.add_column('conversations',
        sa.Column('user_preferences', sa.String(length=500), nullable=True)
    )

def downgrade() -> None:
    # Remove the column - data will be lost!
    op.drop_column('conversations', 'user_preferences')
```

### 4. Apply Migration

```bash
uv run alembic upgrade head
```

### 5. Test

Run tests to ensure the migration doesn't break existing functionality:

```bash
uv run pytest tests/integration/test_database.py -v
```

## Migration Best Practices

### Auto-Generated Migrations

**Use for:**
- Simple column additions/removals
- Table creation
- Index changes
- Foreign key additions

**Review carefully:**
- Data type compatibility
- Null constraints
- Default values
- Index creation order

### Manual Migrations

**Use when:**
- Complex data transformations needed
- Multiple dependent changes
- Custom SQL required
- Backward compatibility with data preservation

```python
def upgrade() -> None:
    # Custom data migration
    op.execute("""
        UPDATE conversations
        SET user_preferences = '{"theme": "dark"}'
        WHERE user_preferences IS NULL
    """)

    # Add column with NOT NULL constraint after populating
    op.add_column('conversations',
        sa.Column('user_preferences', sa.String(500),
                 nullable=False, server_default='"{}"')
    )
```

### Data Safety

```python
# NEVER drop columns with important data without backup
def upgrade() -> None:
    # Always backup data before destructive operations
    op.execute("CREATE TABLE conversations_backup AS SELECT * FROM conversations")
    op.drop_column('conversations', 'old_column')
```

## Special Considerations

### SQLite Limitations

- No schema renaming (`op.rename_table()` doesn't work)
- No column type changes in most cases
- Limited foreign key support (must enable with `PRAGMA foreign_keys`)
- Transactional constraints on certain operations

### Handling Large Databases

For migrations affecting large datasets:

```python
# Batch processing for large tables
BATCH_SIZE = 1000

def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute("SELECT id FROM conversations")

    for batch in batch_results(result, BATCH_SIZE):
        conn.execute("""
            UPDATE conversations
            SET status = 'processed'
            WHERE id IN :batch_ids
        """, {"batch_ids": batch})

        conn.commit()  # Commit between batches
```

### Alembic Configuration

Current settings in `alembic.ini`:

```ini
[alembic]
# Path to migration scripts (same directory as config)
script_location = migrations

# Template used to generate migration files
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

# Timezone for timestamps
timezone = UTC

# Truncate long revisions in log display
truncate_slug_length = 40
```

**Note**: Database URL is dynamically set from `src.config.settings` in `env.py`, not in the config file.

## Testing Migrations

### Unit Tests for Migrations

```python
# tests/migration_test.py
def test_migration_up_down():
    """Test that upgrade/downgrade operations are reversible"""

    # Test upgrade
    script = MigrationContext.from_environment()
    script.upgrade('head')

    # Verify table/column exists
    engine = create_engine("sqlite:///:memory:")
    inspector = inspect(engine)
    assert 'conversations' in inspector.get_table_names()

    # Test downgrade
    script.downgrade('base')

    # Verify removal
    inspector = inspect(engine)
    assert 'conversations' not in inspector.get_table_names()
```

### Integration Tests

```python
# tests/integration/test_migrations.py
def test_migration_integration():
    """Test migration with real database"""

    # Run migrations
    call_command("upgrade", "head")

    # Verify database state
    with test_session() as session:
        # Test that tables exist and data is preserved
        result = session.query(ConversationORM).count()
        assert result >= 0
```

## Common Patterns

### Adding a New Table

```python
def upgrade() -> None:
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('preferences', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['conversations.id']),
    )
```

### Adding an Index

```python
def upgrade() -> None:
    op.create_index(
        'idx_conversations_user_id',
        'conversations',
        ['user_id']
    )
```

### Data Migration

```python
def upgrade() -> None:
    # Migrate old format to new format
    op.execute("""
        UPDATE messages
        SET content = REPLACE(content, '<old>', '<new>')
        WHERE content LIKE '%<old>%'
    """)
```

## Troubleshooting

### Common Issues

**Migration stuck:**
```bash
# Check current state
uv run alembic current

# Reset revision manually (last resort)
alembic stamp head
```

**Database locked:**
```bash
# Close all connections
# SQLite: REPAIR DATABASE
# Alembic: Try again after a few seconds
```

**Migration conflicts:**
```bash
# Clean environment
rm -rf migrations/versions/*.py
uv run alembic revision --autogenerate -m "new_start"
```

**Async SQLite driver issue:**
The migration environment is configured for async SQLAlchemy, which requires an async SQLite driver. If you get "The asyncio extension requires an async driver to be used" error, the database URL needs to use `aiosqlite`.

**Current Configuration:**
- Settings default: `sqlite:///data/botsalinha.db` (synchronous)
- Repository converts to: `sqlite+aiosqlite:///data/botsalinha.db` (asynchronous)
- Migration env.py: Uses settings URL directly (needs conversion)

**To fix:**
1. **Option 1: Use the correct environment variable**
   ```bash
   # Set the async URL directly
   export DATABASE__URL="sqlite+aiosqlite:///data/botsalinha.db"
   ```

2. **Option 2: Run migrations with a database that has async URL**
   ```bash
   # Create a temporary env var for migrations
   DATABASE__URL="sqlite+aiosqlite:///:memory:" uv run alembic -c migrations/alembic.ini current
   ```

3. **Option 3: Fix the migration environment**
   The `migrations/env.py` needs to convert the URL like `sqlite_repository.py` does.

**Note:** Use `DATABASE__URL="sqlite+aiosqlite:///:memory:"` for testing migrations without affecting your actual database.

### Debug Mode

Enable detailed logging:

```bash
uv run alembic upgrade --tag head --sql
```

This prints the SQL without executing it.

### Configuration Issues

If you encounter "Path doesn't exist" errors, ensure you're in the correct directory when running alembic commands:

```bash
# From project root (recommended)
uv run alembic -c migrations/alembic.ini current

# Or from migrations directory
cd migrations && uv run alembic current
```

The `script_location` in `alembic.ini` points to the `migrations` directory itself, which contains the configuration files and the `versions/` subdirectory.

## Safety Checklist

Before applying migrations:

- [ ] Back up the database
- [ ] Test migration in development environment
- [ ] Review generated SQL for destructive operations
- [ ] Check for data loss scenarios
- [ ] Verify rollback works correctly
- [ ] Run full test suite after migration
- [ ] Monitor database performance after migration

## AI Agent Instructions

When working with migrations:

1. **Always run `uv run alembic revision --autogenerate -m "description"` after modifying `src/models/`**
2. **Review generated migration files before applying them**
3. **Test migrations in development before production**
4. **Create manual migrations for complex data transformations**
5. **Include rollback operations for all changes**
6. **Document data migrations clearly**
7. **Never apply migrations to production without backup**

Remember: Migrations are permanent and can cause data loss if not handled carefully.