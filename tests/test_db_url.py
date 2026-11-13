"""Offline tests for src/db_url.py. No database, no network."""

import pytest

from src.db_url import DatabaseUrlError, to_sqlalchemy_url


def test_plain_postgresql_gets_the_psycopg_driver():
    url = to_sqlalchemy_url("postgresql://u:p@127.0.0.1:5434/tb")
    assert url == "postgresql+psycopg://u:p@127.0.0.1:5434/tb"


def test_short_postgres_scheme_is_accepted_too():
    url = to_sqlalchemy_url("postgres://u:p@127.0.0.1:5434/tb")
    assert url == "postgresql+psycopg://u:p@127.0.0.1:5434/tb"


def test_a_named_driver_is_left_alone():
    raw = "postgresql+psycopg://u:p@127.0.0.1:5434/tb"
    assert to_sqlalchemy_url(raw) == raw


def test_another_named_driver_is_left_alone():
    raw = "postgresql+asyncpg://u:p@127.0.0.1:5434/tb"
    assert to_sqlalchemy_url(raw) == raw


def test_surrounding_space_is_ignored():
    url = to_sqlalchemy_url("  postgresql://u:p@h/tb\n")
    assert url == "postgresql+psycopg://u:p@h/tb"


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_an_empty_value_is_refused(raw):
    with pytest.raises(DatabaseUrlError) as err:
        to_sqlalchemy_url(raw)
    assert "DATABASE_URL" in str(err.value)


def test_another_database_is_refused():
    with pytest.raises(DatabaseUrlError):
        to_sqlalchemy_url("mysql://u:p@h/tb")


def test_the_password_is_not_in_the_error_text():
    with pytest.raises(DatabaseUrlError) as err:
        to_sqlalchemy_url("mysql://user:hunter2@host/tb")
    assert "hunter2" not in str(err.value)
    assert "user" not in str(err.value)
