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
`.env`, outside the repository, and deletes dumps older than 14 days. It
fails loudly and keeps nothing if the dump comes out empty.

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
