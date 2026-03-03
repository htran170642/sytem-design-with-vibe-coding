"""
Alembic Migration Environment
Configured for synchronous execution against the PostgreSQL database.
The async engine's underlying sync engine is used so no psycopg2 is required.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make app importable from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings  # noqa: E402

# Alembic Config object (provides access to alembic.ini values)
config = context.config

# Set the database URL from application settings (overrides alembic.ini placeholder)
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic can detect schema changes
from app.db import Base  # noqa: E402
from app.models import *  # noqa: E402, F401, F403 — registers all models with Base.metadata

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (generates SQL without a live connection).
    Useful for generating migration scripts to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode (connects to the DB and applies migrations).
    Uses the synchronous database URL so no asyncpg event loop is needed.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
