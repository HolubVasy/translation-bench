"""Alembic entry point (AB#300).

IO at the edges: this file reads the environment and opens the connection.
The one piece of logic, naming the driver, lives in src/db_url.py and has
its own offline tests.

target_metadata stays None on purpose. There are no SQLAlchemy models in
this repository and autogenerate has nothing to compare against; revisions
carry plain SQL, which is what the schema is written in.
"""

import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db_url import to_sqlalchemy_url  # noqa: E402

target_metadata = None


def run_offline(url):
    """Print the SQL of every pending revision instead of running it."""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_online(url):
    """Connect and run every revision that has not run yet."""
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


database_url = to_sqlalchemy_url(os.environ.get("DATABASE_URL"))

if context.is_offline_mode():
    run_offline(database_url)
else:
    run_online(database_url)
