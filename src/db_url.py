"""The one place that decides which connection string the app uses.

Config over code: the string itself lives in DATABASE_URL, never here. This
module only names the driver, because SQLAlchemy needs to be told which one
to load and a bare postgresql:// would reach for psycopg2, which is not
installed.
"""

DRIVER = "postgresql+psycopg"

PLAIN_PREFIXES = ("postgresql://", "postgres://")


class DatabaseUrlError(Exception):
    """DATABASE_URL is missing or is not a PostgreSQL connection string."""


def to_sqlalchemy_url(raw):
    """Return raw with the psycopg driver named.

    A string that already names a driver is returned untouched, so a reader
    can pin a different one in .env without editing code.
    """
    url = (raw or "").strip()
    if not url:
        raise DatabaseUrlError(
            "DATABASE_URL is not set (see .env.example)")
    for prefix in PLAIN_PREFIXES:
        if url.startswith(prefix):
            return DRIVER + "://" + url[len(prefix):]
    if url.startswith(DRIVER + "://"):
        return url
    if url.startswith("postgresql+"):
        return url
    raise DatabaseUrlError(
        "DATABASE_URL is not a PostgreSQL connection string: "
        + _masked(url))


def _masked(url):
    """Return url with anything before the host replaced, for error text."""
    marker = "://"
    at = url.rfind("@")
    start = url.find(marker)
    if start < 0 or at < 0 or at < start:
        return url.split(marker)[0] + marker + "..."
    return url[: start + len(marker)] + "..." + url[at:]
