"""Initial schema: thirty-one tables for the Translator interview app.

Revision ID: 0001
Revises:
Create Date: 2026-11-13

The DDL is not written out as op.create_table calls. It lives beside this
file as plain SQL, in migrations/sql/, because that is the form the owner's
draw.io file and the wiki page are checked against: thirty-one tables and
forty-five foreign keys, countable in either direction.
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def read_sql(name):
    """Return the text of one statement file next to this revision."""
    return (SQL_DIR / name).read_text(encoding="utf-8")


def upgrade():
    op.execute(read_sql("0001_schema.up.sql"))


def downgrade():
    op.execute(read_sql("0001_schema.down.sql"))
