# Database on the VPS

PostgreSQL for the Translator interview app, story 20 on the board (AB#297).
One container, one named volume, nothing reachable from the internet.

The schema is drawn and explained on the board wiki page "Translator
interview diagrams". Here is how it is built and kept.

## What exists

    docker-compose.yml       one service, db, image postgres:17-alpine
    .env                     database name, user, password, DATABASE_URL
    alembic.ini              migration settings, no connection string in it
    migrations/              Alembic: env.py, versions/, and the SQL itself
    scripts/db_backup.sh     one dump a day, the last 14 kept

The port is published on `127.0.0.1`, not `0.0.0.0`. The database answers to
the VPS itself and to an SSH tunnel, to nothing else. There is no rule to add
to the firewall and no password to rotate after a leak that a port scan would
have caused.

The host port is `DB_PORT` from `.env`, default 5434. It is not 5432 because
the VPS already runs other Postgres containers: `job_search_db` holds
`127.0.0.1:5432` and `archive_db` holds `127.0.0.1:5433`. Inside the
container the port is 5432 as always, so only `DATABASE_URL` and the tunnel
care. Check what is taken before the first run:

    docker ps --format "{{.Names}} :: {{.Ports}}" | grep 5432

## First run

On the VPS, in `~/workspace/translation-bench`:

    cp .env.example .env
    # open .env and set POSTGRES_PASSWORD and DATABASE_URL to a real password
    chmod 600 .env
    docker compose up -d
    docker compose ps

`docker compose ps` has to show the service healthy. The healthcheck is
`pg_isready`, so healthy means the server answers, not only that the process
started.

To check the connection without printing the password:

    docker compose exec db psql -U "$(grep '^POSTGRES_USER=' .env | cut -d= -f2-)" \
        -d "$(grep '^POSTGRES_DB=' .env | cut -d= -f2-)" -c '\l'

## Migrations

Alembic owns the order and the record of what has run. The DDL itself is
plain SQL in `migrations/sql/`, run by a revision in `migrations/versions/`.
There are no SQLAlchemy models in this repository, so autogenerate has
nothing to compare against and is not used; a new revision carries SQL.

The connection string is never in `alembic.ini`. `env.py` reads
`DATABASE_URL` from the environment, the same rule the OpenRouter key
follows, so export `.env` before running anything:

    set -a; . ./.env; set +a
    alembic upgrade head
    alembic current

Undoing and inspecting:

    alembic downgrade base        back to an empty database
    alembic upgrade head --sql    print the SQL, run nothing

A revision is never edited once it has run anywhere. A mistake is corrected
by the next revision, for the same reason a cut or a score is never
overwritten: something already points at what was there.

The schema is the one thing no offline test can check: it is only real once
PostgreSQL accepts it. So it is checked against a real server rather than
asserted on paper. Apply every revision to an empty PostgreSQL 17, count 31
tables and 45 foreign keys, downgrade to base, check nothing is left.

That sequence becomes the `migrations` job in CI, which pull request 143
adds. It is not in `.github/workflows/ci.yml` on this branch, and that is
deliberate: the reviewing action refuses to run on a pull request that edits
a workflow file, so the workflow change is kept apart from the code it
guards. Until 143 is merged the sequence is run by hand against a throwaway
container, and a revision that cannot be undone is not caught by CI.

## Connecting from your own machine

The port is closed to the outside on purpose, so open a tunnel instead:

    ssh -N -L 5434:127.0.0.1:5434 deploy@<vps>

While that runs, `postgresql://...@127.0.0.1:5434/...` on your machine
reaches the container on the VPS. Use whatever `DB_PORT` says if it changed.

## Backup

`scripts/db_backup.sh` writes one gzipped dump a day into `BACKUP_DIR` from
`.env`, outside the repository, and keeps the newest 14 dumps.

It keeps a count, not an age. If cron fails for three weeks, an age based
rule would delete every surviving dump on the first successful night and
leave one file. Counting keeps the last fourteen whatever their dates are.

The directory is 0700 and the dumps 0600, set by `umask 077` and a `chmod`
on the directory. A dump holds every word of every interview, so no other
user on the VPS can read it. That is the same intent as the loopback-only
port: the data does not become readable just because someone has a shell.

A failed dump never replaces a good one. The script dumps to a temporary file
first and checks `pg_dump` on its own, because in `pg_dump | gzip` the shell
reports gzip's status, and gzip turns an empty input into a valid short file
that looks like a backup. Today's dump is replaced only after a non-empty
dump exists, so a night when the container is down leaves yesterday's file
and an error in the cron mail.

Install it in cron:

    chmod +x scripts/db_backup.sh
    crontab -e
    # 15 3 * * * /home/deploy/workspace/translation-bench/scripts/db_backup.sh

Restoring one dump into an empty database:

    gunzip -c /path/to/translation_bench-2026-11-14.sql.gz | \
        docker compose exec -T db psql -U <user> -d <database>

A dump is only a backup once it has been restored at least once. Do that on
a throwaway database before trusting the cron line.

## What is deliberately not here

- No port open to the internet, so no password is the only thing between the
  data and a scanner.
- No connection string in git. `.env` is gitignored and is the one place it
  lives, as the repository rule says.
- No migrations yet. The schema arrives with its own story and its own PR.
