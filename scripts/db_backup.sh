#!/bin/sh
# Daily dump of the Translator interview database (AB#297).
#
# Cron on the VPS, 03:15 every night:
#   15 3 * * * /home/deploy/workspace/translation-bench/scripts/db_backup.sh
#
# Reads POSTGRES_DB, POSTGRES_USER and BACKUP_DIR from the .env next to the
# compose file. The password stays inside the container and is never read,
# printed or written into a file name. Keeps the last 14 dumps.

set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
env_file="$repo_dir/.env"

if [ ! -f "$env_file" ]; then
    echo "db_backup: no .env next to docker-compose.yml" >&2
    exit 1
fi

read_env() {
    grep "^$1=" "$env_file" | head -1 | cut -d= -f2- || true
}

db_name=$(read_env POSTGRES_DB)
db_user=$(read_env POSTGRES_USER)
backup_dir=$(read_env BACKUP_DIR)

if [ -z "$db_name" ] || [ -z "$db_user" ]; then
    echo "db_backup: POSTGRES_DB or POSTGRES_USER missing from .env" >&2
    exit 1
fi

if [ -z "$backup_dir" ]; then
    backup_dir="$HOME/backups/translation-bench"
fi

mkdir -p "$backup_dir"
stamp=$(date -u +%Y-%m-%d)
target="$backup_dir/$db_name-$stamp.sql.gz"

cd "$repo_dir"
docker compose exec -T db pg_dump -U "$db_user" -d "$db_name" | gzip > "$target"

if [ ! -s "$target" ]; then
    echo "db_backup: the dump is empty, keeping nothing" >&2
    rm -f "$target"
    exit 1
fi

find "$backup_dir" -name "$db_name-*.sql.gz" -type f -mtime +14 -delete

echo "db_backup: wrote $target"
