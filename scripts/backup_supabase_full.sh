#!/usr/bin/env bash
set -euo pipefail

# Supabase complete backup script (self-hosted)
# - PostgreSQL dumps: custom + plain SQL + globals
# - Optional Docker volume snapshots for storage/config
# - Archive + SHA256 + retention cleanup

OUTPUT_DIR="${OUTPUT_DIR:-/root/BotSalinha/backups/supabase}"
MODE="${MODE:-auto}"            # auto|docker|direct
DB_CONTAINER="${DB_CONTAINER:-}"
DB_HOST="${DB_HOST:-}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-postgres}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-${PGPASSWORD:-}}"
ENV_FILE="${ENV_FILE:-}"
VOLUME_REGEX="${VOLUME_REGEX:-^(supabase_db_config|supabase_storage|minio_data)$}"
INCLUDE_VOLUMES="${INCLUDE_VOLUMES:-true}"
RETENTION_DAYS="${RETENTION_DAYS:-0}"
DRY_RUN="false"

usage() {
  cat <<'EOF'
Usage: backup_supabase_full.sh [options]

Options:
  --output-dir <dir>         Backup output directory (default: /root/BotSalinha/backups/supabase)
  --env-file <file>          Optional env file to source before running
  --mode <auto|docker|direct>
  --db-container <name>      Docker container name (docker mode)
  --db-host <host>           PostgreSQL host (direct mode)
  --db-port <port>           PostgreSQL port (default: 5432)
  --db-name <name>           Database name (default: postgres)
  --db-user <user>           Database user (default: postgres)
  --db-password <pass>       Database password (direct mode)
  --volume-regex <regex>     Regex for Docker volumes to snapshot
                              (default: ^(supabase_db_config|supabase_storage|minio_data)$)
  --include-volumes <true|false>  Include Docker volume snapshots (default: true)
  --retention-days <n>       Delete backup archives older than n days (0 = keep all)
  --dry-run                  Print actions without executing
  -h, --help                 Show this help

Examples:
  ./scripts/backup_supabase_full.sh
  ./scripts/backup_supabase_full.sh --env-file .env.production
  ./scripts/backup_supabase_full.sh --mode docker --db-container supabase_supabase_db.1.xxxxx
  ./scripts/backup_supabase_full.sh --mode direct --db-host supabase_db --db-password 'secret'
  ./scripts/backup_supabase_full.sh --mode direct --db-host 127.0.0.1 --db-password 'secret'
EOF
}

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

run() {
  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY-RUN: $*"
    return 0
  fi
  eval "$@"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --db-container) DB_CONTAINER="$2"; shift 2 ;;
    --db-host) DB_HOST="$2"; shift 2 ;;
    --db-port) DB_PORT="$2"; shift 2 ;;
    --db-name) DB_NAME="$2"; shift 2 ;;
    --db-user) DB_USER="$2"; shift 2 ;;
    --db-password) DB_PASSWORD="$2"; shift 2 ;;
    --volume-regex) VOLUME_REGEX="$2"; shift 2 ;;
    --include-volumes) INCLUDE_VOLUMES="$2"; shift 2 ;;
    --retention-days) RETENTION_DAYS="$2"; shift 2 ;;
    --dry-run) DRY_RUN="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) log "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    log "Env file not found: $ENV_FILE"
    exit 1
  fi
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
  # Re-apply effective defaults for values optionally provided by env file.
  DB_PASSWORD="${DB_PASSWORD:-${PGPASSWORD:-}}"
  VOLUME_REGEX="${VOLUME_REGEX:-^(supabase_db_config|supabase_storage|minio_data)$}"
fi

if [[ "$MODE" != "auto" && "$MODE" != "docker" && "$MODE" != "direct" ]]; then
  log "Invalid mode: $MODE"
  exit 1
fi

if [[ "$INCLUDE_VOLUMES" != "true" && "$INCLUDE_VOLUMES" != "false" ]]; then
  log "Invalid --include-volumes value: $INCLUDE_VOLUMES"
  exit 1
fi

TIMESTAMP="$(date -u +'%Y%m%d_%H%M%S')"
BASE_NAME="supabase_full_backup_${TIMESTAMP}"
WORK_DIR="${OUTPUT_DIR}/${BASE_NAME}"
ARCHIVE_PATH="${OUTPUT_DIR}/${BASE_NAME}.tar.gz"
ARCHIVE_SHA256="${ARCHIVE_PATH}.sha256"

mkdir -p "$OUTPUT_DIR"
run "mkdir -p '$WORK_DIR' '$WORK_DIR/db' '$WORK_DIR/meta' '$WORK_DIR/volumes'"

if [[ "$MODE" == "auto" ]]; then
  if command -v docker >/dev/null 2>&1; then
    MODE="docker"
  else
    MODE="direct"
  fi
fi

if [[ "$MODE" == "docker" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    log "docker command not found"
    exit 1
  fi

  if [[ -z "$DB_CONTAINER" ]]; then
    DB_CONTAINER="$(
      docker ps --format '{{.Names}}' \
        | rg '^(supabase_supabase_db|supabase_db|supabase-db|db)(\.|$)' -m1 \
        || true
    )"
  fi

  if [[ -z "$DB_CONTAINER" ]]; then
    log "Could not auto-detect Supabase DB container. Use --db-container."
    exit 1
  fi

  log "Using docker mode with DB container: $DB_CONTAINER"

  run "docker exec '$DB_CONTAINER' psql -U '$DB_USER' -d '$DB_NAME' -Atc 'select version();' > '$WORK_DIR/meta/postgres_version.txt'"
  run "docker exec '$DB_CONTAINER' psql -U '$DB_USER' -d '$DB_NAME' -Atc \"select datname from pg_database where datistemplate = false order by datname;\" > '$WORK_DIR/meta/databases.txt'"

  log "Creating PostgreSQL dumps..."
  run "docker exec '$DB_CONTAINER' pg_dump -U '$DB_USER' -d '$DB_NAME' -Fc > '$WORK_DIR/db/${DB_NAME}.dump'"
  run "docker exec '$DB_CONTAINER' pg_dump -U '$DB_USER' -d '$DB_NAME' --clean --if-exists --no-owner --no-privileges > '$WORK_DIR/db/${DB_NAME}.sql'"
  run "docker exec '$DB_CONTAINER' pg_dumpall -U '$DB_USER' --globals-only > '$WORK_DIR/db/globals.sql'"

  if [[ "$INCLUDE_VOLUMES" == "true" ]]; then
    log "Backing up Docker volumes..."
    mapfile -t VOLS < <(docker volume ls --format '{{.Name}}' | rg "$VOLUME_REGEX" || true)
    if [[ "${#VOLS[@]}" -eq 0 ]]; then
      log "No Docker volumes matched regex: $VOLUME_REGEX"
    fi
    for vol in "${VOLS[@]:-}"; do
      [[ -z "$vol" ]] && continue
      log "Volume: $vol"
      run "docker run --rm -v '${vol}:/from:ro' -v '$WORK_DIR/volumes:/to' alpine sh -c 'cd /from && tar -czf /to/${vol}.tar.gz .'"
    done
    if [[ "$DRY_RUN" != "true" ]]; then
      printf '%s\n' "${VOLS[@]:-}" > "$WORK_DIR/meta/volumes.txt"
    else
      log "DRY-RUN: write volume list to '$WORK_DIR/meta/volumes.txt'"
    fi
  fi

else
  if ! command -v pg_dump >/dev/null 2>&1 || ! command -v pg_dumpall >/dev/null 2>&1 || ! command -v psql >/dev/null 2>&1; then
    log "direct mode requires psql, pg_dump and pg_dumpall installed"
    exit 1
  fi
  if [[ -z "$DB_HOST" ]]; then
    log "direct mode requires --db-host or DB_HOST"
    exit 1
  fi

  log "Using direct mode with host: $DB_HOST:$DB_PORT"
  export PGPASSWORD="$DB_PASSWORD"

  run "psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' -d '$DB_NAME' -Atc 'select version();' > '$WORK_DIR/meta/postgres_version.txt'"
  run "psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' -d '$DB_NAME' -Atc \"select datname from pg_database where datistemplate = false order by datname;\" > '$WORK_DIR/meta/databases.txt'"

  log "Creating PostgreSQL dumps..."
  run "pg_dump -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' -d '$DB_NAME' -Fc > '$WORK_DIR/db/${DB_NAME}.dump'"
  run "pg_dump -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' -d '$DB_NAME' --clean --if-exists --no-owner --no-privileges > '$WORK_DIR/db/${DB_NAME}.sql'"
  run "pg_dumpall -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' --globals-only > '$WORK_DIR/db/globals.sql'"
fi

if [[ "$DRY_RUN" != "true" ]]; then
cat > "$WORK_DIR/meta/README_RESTORE.txt" <<EOF
Supabase full backup created at: $(date -u +'%Y-%m-%dT%H:%M:%SZ')
Mode: $MODE
Database: $DB_NAME
User: $DB_USER

Restore order (PostgreSQL):
1) roles/globals:
   psql -U <admin> -f db/globals.sql
2) database schema+data (custom preferred):
   pg_restore -U <admin> -d <target_db> --clean --if-exists db/${DB_NAME}.dump
   or plain SQL:
   psql -U <admin> -d <target_db> -f db/${DB_NAME}.sql
3) optional volumes:
   extract tar.gz files from volumes/ to their respective Docker volumes.
EOF
else
  log "DRY-RUN: write restore instructions to '$WORK_DIR/meta/README_RESTORE.txt'"
fi

if [[ "$DRY_RUN" != "true" ]]; then
  (cd "$WORK_DIR" && find . -type f -print0 | xargs -0 sha256sum > "$WORK_DIR/meta/MANIFEST.sha256")
fi

log "Creating final archive: $ARCHIVE_PATH"
run "tar -C '$OUTPUT_DIR' -czf '$ARCHIVE_PATH' '$BASE_NAME'"

if [[ "$DRY_RUN" != "true" ]]; then
  sha256sum "$ARCHIVE_PATH" > "$ARCHIVE_SHA256"
fi

run "rm -rf '$WORK_DIR'"

if [[ "$RETENTION_DAYS" -gt 0 ]]; then
  log "Applying retention: ${RETENTION_DAYS} days"
  run "find '$OUTPUT_DIR' -maxdepth 1 -type f -name 'supabase_full_backup_*.tar.gz' -mtime +$RETENTION_DAYS -delete"
  run "find '$OUTPUT_DIR' -maxdepth 1 -type f -name 'supabase_full_backup_*.tar.gz.sha256' -mtime +$RETENTION_DAYS -delete"
fi

log "Backup completed"
log "Archive: $ARCHIVE_PATH"
log "Checksum: $ARCHIVE_SHA256"
