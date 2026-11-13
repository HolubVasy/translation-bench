# Database on the VPS

PostgreSQL for the Translator interview app, story 20 on the board (AB#297).
One container, one named volume, nothing reachable from the internet.

The schema itself is not here. It is drawn and explained on the board wiki
page "Translator interview diagrams" and is built by migrations in a later
story (AB#300).

## What exists

    docker-compose.yml       one service, db, image postgres:17-alpine
    .env                     database name, user, password, DATABASE_URL
    scripts/db_backup.sh     one dump a day, the last 14 kept

The port is published as `127.0.0.1:5432`, not `0.0.0.0`. The database
answers to the VPS itself and to an SSH tunnel, to nothing else. There is no
rule to add to the firewall and no password to rotate after a leak that a
port scan would have caused.

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

## Connecting from your own machine

The port is closed to the outside on purpose, so open a tunnel instead:

    ssh -N -L 5432:127.0.0.1:5432 deploy@<vps>

While that runs, `postgresql://...@127.0.0.1:5432/...` on your machine
reaches the container on the VPS.

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
