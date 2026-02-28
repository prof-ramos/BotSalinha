# AGENTS.md — Migration Files

Parent reference: ../../AGENTS.md

---

## Overview

The `migrations/versions/` directory contains individual Alembic migration files that track database schema changes over time. Each migration represents a specific change to the ORM models and includes both auto-generated and manually crafted migrations.

---

## Migration Patterns

### Auto-generated Migrations
- Created automatically when running `uv run alembic revision --autogenerate -m "description"`
- Track changes to ORM models in `src/models/`
- Include upgrade/downgrade logic for schema changes
- Follow naming convention: `{revision}_{description}.py`

### Manual Migrations
- Created manually for complex schema changes that alembic can't auto-detect
- Include custom upgrade/downgrade logic
- Used for data migrations, constraints, or complex transformations

### Key Principles
- **Never edit existing migrations** - Each migration represents a historical state
- **Always create new migration for changes** - Don't modify history
- **Test migrations in development first** - Apply with `uv run alembic upgrade head`
- **Use alembic upgrade head to apply** - Can test migrations in isolation

---

## Migration Structure

```python
"""add_conversation_table

Revision ID: 001
Revises: None
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add table creation logic here
    pass

def downgrade() -> None:
    # Add table deletion logic here
    pass
```

---

## AI Agent Instructions

When working with migrations:

1. **Model Changes First**
   - Always modify ORM models in `src/models/` before generating migrations
   - Run `uv run alembic revision --autogenerate -m "description"`
   - Review the generated migration file

2. **Testing Migrations**
   ```bash
   # Test upgrade
   uv run alembic upgrade head

   # Test downgrade
   uv run alembic downgrade -1
   ```

3. **Complex Migrations**
   - For data migrations or complex transformations, create manual migrations
   - Include detailed comments explaining the migration purpose
   - Handle edge cases and error conditions

4. **Migration Dependencies**
   - Each migration depends on the previous one
   - Track relationships with `down_revision` and `depends_on`
   - Maintain correct chronological order

---

## Common Patterns

### Adding a New Table
```python
def upgrade() -> None:
    op.create_table(
        'new_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('new_table')
```

### Adding a Column
```python
def upgrade() -> None:
    op.add_column('existing_table',
        sa.Column('new_column', sa.String(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column('existing_table', 'new_column')
```

### Data Migration
```python
def upgrade() -> None:
    op.execute("UPDATE users SET status = 'active' WHERE created_at > '2024-01-01'")

def downgrade() -> None:
    op.execute("UPDATE users SET status = NULL WHERE created_at > '2024-01-01'")
```

### Index Creation
```python
def upgrade() -> None:
    op.create_index('idx_conversation_user', 'conversations', ['user_id'])

def downgrade() -> None:
    op.drop_index('idx_conversation_user')
```

---

## Dependencies

Migration files depend on:
- **ORM Models**: All changes start in `src/models/`
- **Alembic Configuration**: `alembic.ini` and `env.py`
- **Repository Pattern**: Changes must be reflected in repository implementations
- **Application Code**: Migration tests should include integration tests

---

## Monitoring and Maintenance

### Check Migration Status
```bash
# Show current revision
uv run alembic current

# Show revision history
uv run alembic history

# Show pending migrations
uv run alembic current
```

### Best Practices
1. **Atomic migrations**: Each migration should be self-contained
2. **Rollback capability**: Always implement downgrade
3. **Data safety**: Test migrations with real data when possible
4. **Documentation**: Include clear comments explaining migration purpose
5. **Version control**: Keep migrations in version control
6. **CI/CD**: Include migration tests in CI pipeline

---

## Troubleshooting

### Common Issues

**Migration conflicts**:
- Ensure only one migration runs at a time
- Check for stale migration locks

**Data loss**:
- Always backup before running migrations
- Test migrations on staging first

**Dependency issues**:
- Check `down_revision` references are correct
- Ensure migration order is chronological

### Recovery Steps
1. If a migration fails, identify the error
2. Fix the issue in the migration file
3. Reset migration state if needed
4. Test the fixed migration
5. Apply the corrected migration